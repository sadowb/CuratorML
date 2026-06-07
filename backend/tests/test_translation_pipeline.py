"""Tests for the translation pipeline (Packet 10).

Covers:
  * Request validation (stage-specific options)
  * LLM response schema parsing and deduplication
  * Prompt builder pure-function behavior
  * Translation gateway JSON extraction and repair
  * Translation service OCR fallback, overwrite/protection, status transitions
  * Edge cases: empty page, no-op retry, concurrent duplicate
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.schemas.job import InpaintOptions, JobSubmitRequest
from app.schemas.translation import (
    LLMTranslationLine,
    LLMTranslationResponse,
    ProviderOverride,
    TranslateOptions,
)
from app.services.translation_errors import (
    TranslationDuplicateRunError,
    TranslationInvalidJSONError,
    TranslationLanguageResolutionError,
    TranslationSchemaMismatchError,
)
from app.services.translation_gateway import TranslationGateway
from app.services.translation_prompt import build_translation_prompt


# ═══════════════════════════════════════════════════════════════════════
# Packet 2: Request validation tests
# ═══════════════════════════════════════════════════════════════════════


class TestJobSubmitRequestValidation:
    """Stage-specific validation on JobSubmitRequest."""

    def test_translate_requires_options(self):
        with pytest.raises(ValueError, match="translate_options is required"):
            JobSubmitRequest(stage="translate")

    def test_translate_accepts_options(self):
        req = JobSubmitRequest(
            stage="translate",
            translate_options=TranslateOptions(target_language="en"),
        )
        assert req.translate_options is not None
        assert req.translate_options.target_language == "en"

    def test_non_translate_rejects_options(self):
        with pytest.raises(ValueError, match="must not be provided"):
            JobSubmitRequest(
                stage="ocr",
                translate_options=TranslateOptions(target_language="en"),
            )

    def test_non_translate_without_options_ok(self):
        req = JobSubmitRequest(stage="mask_inference")
        assert req.translate_options is None

    def test_inpaint_accepts_inpaint_options(self):
        req = JobSubmitRequest(
            stage="inpaint",
            inpaint_options=InpaintOptions(
                method="telea",
                radius=4,
                ai_expand_strength=0.3,
            ),
        )
        assert req.inpaint_options is not None
        assert req.inpaint_options.method == "telea"

    def test_inpaint_text_grow_accepts_40(self):
        req = JobSubmitRequest(
            stage="inpaint",
            inpaint_options=InpaintOptions(text_expand_px=40),
        )
        assert req.inpaint_options is not None
        assert req.inpaint_options.text_expand_px == 40

    def test_inpaint_text_grow_rejects_values_above_40(self):
        with pytest.raises(ValueError, match="less than or equal to 40"):
            InpaintOptions(text_expand_px=41)

    def test_inpaint_requires_options(self):
        with pytest.raises(ValueError, match="inpaint_options is required"):
            JobSubmitRequest(stage="inpaint")

    def test_inpaint_accepts_legacy_flat_options_payload(self):
        req = JobSubmitRequest.model_validate(
            {
                "stage": "inpaint",
                "method": "ns",
                "radius": 8,
                "ai_expand_strength": 0.6,
                "balloon_safe_inset_mode": "manual",
                "balloon_safe_inset_px": 5,
                "clip_fallback_mode": "inset_bbox",
            }
        )
        assert req.inpaint_options is not None
        assert req.inpaint_options.method == "ns"
        assert req.inpaint_options.radius == 8
        assert req.inpaint_options.clip_fallback_mode == "inset_bbox"

    def test_non_inpaint_rejects_inpaint_options(self):
        with pytest.raises(ValueError, match="inpaint_options must not be provided"):
            JobSubmitRequest(
                stage="ocr",
                inpaint_options=InpaintOptions(),
            )


# ═══════════════════════════════════════════════════════════════════════
# Packet 3: LLM schema parse tests
# ═══════════════════════════════════════════════════════════════════════


class TestLLMTranslationResponse:
    """Schema validation and order deduplication."""

    def test_valid_response_parses(self):
        data = {
            "page_summary": "A fight scene",
            "lines": [
                {
                    "order": 1,
                    "source_text": "やめろ",
                    "literal_translation": "Stop it",
                    "natural_translation": "Cut it out!",
                },
                {
                    "order": 2,
                    "source_text": "何だ",
                    "literal_translation": "What is it",
                    "natural_translation": "What the...?",
                },
            ],
        }
        resp = LLMTranslationResponse.model_validate(data)
        assert len(resp.lines) == 2
        assert resp.page_summary == "A fight scene"

    def test_duplicate_orders_keep_first(self):
        data = {
            "lines": [
                {
                    "order": 1,
                    "source_text": "first",
                    "literal_translation": "first",
                    "natural_translation": "FIRST_WINS",
                },
                {
                    "order": 1,
                    "source_text": "dupe",
                    "literal_translation": "dupe",
                    "natural_translation": "DUPE_LOST",
                },
            ],
        }
        resp = LLMTranslationResponse.model_validate(data)
        assert len(resp.lines) == 1
        assert resp.lines[0].natural_translation == "FIRST_WINS"

    def test_invalid_order_zero_rejected(self):
        data = {
            "lines": [
                {
                    "order": 0,
                    "source_text": "bad",
                    "literal_translation": "bad",
                    "natural_translation": "bad",
                },
            ],
        }
        with pytest.raises(Exception):
            LLMTranslationResponse.model_validate(data)

    def test_optional_fields_default_none(self):
        data = {
            "lines": [
                {
                    "order": 1,
                    "source_text": "test",
                    "literal_translation": "test",
                    "natural_translation": "test",
                },
            ],
        }
        resp = LLMTranslationResponse.model_validate(data)
        assert resp.lines[0].speaker_context is None
        assert resp.lines[0].image_explanation is None
        assert resp.page_summary is None


# ═══════════════════════════════════════════════════════════════════════
# Prompt builder tests
# ═══════════════════════════════════════════════════════════════════════


class TestTranslationPromptBuilder:
    """Pure function prompt builder."""

    def test_basic_prompt_structure(self):
        lines = [
            {"order": 1, "text": "こんにちは"},
            {"order": 2, "text": "さようなら"},
        ]
        messages = build_translation_prompt(
            ordered_lines=lines,
            target_language="en",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "en" in messages[1]["content"]
        assert "[1]" in messages[1]["content"]
        assert "[2]" in messages[1]["content"]

    def test_excludes_uuids_and_geometry(self):
        lines = [{"order": 1, "text": "test"}]
        messages = build_translation_prompt(
            ordered_lines=lines,
            target_language="en",
        )
        full_text = json.dumps(messages)
        assert "uuid" not in full_text.lower()
        assert "bbox" not in full_text.lower()
        assert "polygon" not in full_text.lower()

    def test_with_story_context(self):
        messages = build_translation_prompt(
            ordered_lines=[{"order": 1, "text": "test"}],
            target_language="en",
            story_context="A hero fights a villain",
        )
        user_msg = messages[1]["content"]
        assert "A hero fights a villain" in user_msg

    def test_with_memory_block(self):
        messages = build_translation_prompt(
            ordered_lines=[{"order": 1, "text": "ゾロ"}],
            target_language="en",
            memory_block={
                "hard_glossary_rules": [
                    {
                        "source_term": "ゾロ",
                        "preferred_translation": "Zoro",
                        "entry_type": "character",
                    }
                ],
                "soft_notes": [
                    {
                        "source_term": "海軍",
                        "preferred_translation": "Marines",
                        "notes": "Use in this chapter context.",
                    }
                ],
            },
        )
        user_msg = messages[1]["content"]
        assert "HARD GLOSSARY RULES:" in user_msg
        assert "SOFT NOTES:" in user_msg
        assert "ゾロ -> Zoro" in user_msg

    def test_with_helper_image(self):
        messages = build_translation_prompt(
            ordered_lines=[{"order": 1, "text": "test"}],
            target_language="en",
            helper_image_b64="AAAA",
        )
        user_content = messages[1]["content"]
        # With image, user content is a list of content blocks.
        assert isinstance(user_content, list)
        assert user_content[0]["type"] == "image_url"

    def test_thinking_mode_prompt(self):
        messages = build_translation_prompt(
            ordered_lines=[{"order": 1, "text": "test"}],
            target_language="en",
            enable_thinking=True,
        )
        system_text = messages[0]["content"]
        assert "<|think_on|>" in system_text

    def test_no_thinking_by_default(self):
        messages = build_translation_prompt(
            ordered_lines=[{"order": 1, "text": "test"}],
            target_language="en",
        )
        system_text = messages[0]["content"]
        assert "<thinking>" not in system_text

    def test_context_lines_are_not_required_outputs(self):
        messages = build_translation_prompt(
            ordered_lines=[{"order": 2, "text": "translate me"}],
            context_lines=[
                {"order": 1, "text": "manual line"},
                {"order": 2, "text": "translate me"},
            ],
            target_language="en",
        )
        user_msg = messages[1]["content"]
        assert "Full page OCR context for story flow:" in user_msg
        assert "[1] manual line" in user_msg
        assert "Only return JSON line items for orders listed in Lines to translate." in user_msg
        assert "Return exactly one JSON line item for each of these orders, no more and no less: [2]" in user_msg


class TestTranslationInputPlanning:
    def _region(self, region_id: uuid.UUID):
        return SimpleNamespace(id=region_id)

    def _text(
        self,
        *,
        ocr_text_corrected=None,
        ocr_text_raw=None,
        display_text_final=None,
        translation_corrected=None,
        translation_draft=None,
    ):
        return SimpleNamespace(
            ocr_text_corrected=ocr_text_corrected,
            ocr_text_raw=ocr_text_raw,
            display_text_final=display_text_final,
            translation_corrected=translation_corrected,
            translation_draft=translation_draft,
        )

    def test_non_empty_final_translation_protects_but_keeps_context(self):
        from app.services.translation_service import build_translation_inputs

        region_id = uuid.uuid4()
        plan = build_translation_inputs(
            [self._region(region_id)],
            {
                region_id: self._text(
                    ocr_text_raw="raw source",
                    display_text_final="Manual translation",
                )
            },
        )

        assert plan.ordered_lines == []
        assert plan.context_lines == [{"order": 1, "text": "raw source"}]
        assert plan.manual_protected_orders == [1]
        assert plan.order_to_region == {}

    def test_empty_final_translation_does_not_protect(self):
        from app.services.translation_service import build_translation_inputs

        region_id = uuid.uuid4()
        plan = build_translation_inputs(
            [self._region(region_id)],
            {
                region_id: self._text(
                    ocr_text_raw="raw source",
                    display_text_final="   ",
                    translation_corrected="",
                )
            },
        )

        assert plan.ordered_lines == [{"order": 1, "text": "raw source"}]
        assert plan.context_lines == [{"order": 1, "text": "raw source"}]
        assert plan.manual_protected_orders == []
        assert plan.order_to_region == {1: region_id}

    def test_non_empty_corrected_translation_protects(self):
        from app.services.translation_service import build_translation_inputs

        region_id = uuid.uuid4()
        plan = build_translation_inputs(
            [self._region(region_id)],
            {
                region_id: self._text(
                    ocr_text_corrected="edited source",
                    translation_corrected="Manual corrected translation",
                )
            },
        )

        assert plan.ordered_lines == []
        assert plan.context_lines == [{"order": 1, "text": "edited source"}]
        assert plan.manual_protected_orders == [1]

    def test_no_ocr_source_is_excluded_from_target_and_context(self):
        from app.services.translation_service import build_translation_inputs

        region_id = uuid.uuid4()
        plan = build_translation_inputs(
            [self._region(region_id)],
            {region_id: self._text(display_text_final="Manual translation")},
        )

        assert plan.ordered_lines == []
        assert plan.context_lines == []
        assert plan.manual_protected_orders == []
        assert plan.excluded_no_source_orders == [1]


# ═══════════════════════════════════════════════════════════════════════
# Gateway JSON extraction tests
# ═══════════════════════════════════════════════════════════════════════


class TestGatewayJSONExtraction:
    """TranslationGateway._extract_json and _repair_json."""

    def test_clean_json(self):
        raw = '{"lines": [{"order": 1, "source_text": "a", "literal_translation": "b", "natural_translation": "c"}]}'
        result = TranslationGateway._extract_json(raw)
        assert result is not None
        assert result["lines"][0]["order"] == 1

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"lines": []}\n```'
        result = TranslationGateway._extract_json(raw)
        assert result is not None

    def test_json_with_thinking_block(self):
        raw = '<thinking>I need to think</thinking>\n{"lines": []}'
        result = TranslationGateway._extract_json(raw)
        assert result is not None

    def test_repair_trailing_comma(self):
        raw = '{"lines": [{"order": 1,},]}'
        repaired = TranslationGateway._repair_json(raw)
        # After repair, trailing commas should be removed.
        assert ",}" not in repaired
        assert ",]" not in repaired

    def test_repair_strips_fence(self):
        raw = '```json\n{"lines": []}\n```'
        repaired = TranslationGateway._repair_json(raw)
        assert "```" not in repaired

    def test_unparseable_returns_none(self):
        raw = "This is not JSON at all. No braces here."
        result = TranslationGateway._extract_json(raw)
        assert result is None

    def test_schema_rescue_does_not_append_late_system_message(self):
        messages = [
            {"role": "system", "content": "translate as JSON"},
            {"role": "user", "content": "Lines to translate:\n[1] text"},
        ]

        rescue_messages = TranslationGateway._build_schema_rescue_messages(messages)

        assert rescue_messages[0]["role"] == "system"
        assert [message["role"] for message in rescue_messages[1:]] == ["user", "user"]
        assert "strict JSON API" in rescue_messages[-1]["content"]

    def test_json_recovery_does_not_append_late_system_message(self):
        messages = [
            {"role": "system", "content": "translate as JSON"},
            {"role": "user", "content": "Lines to translate:\n[1] text"},
        ]

        recovery_messages = TranslationGateway._build_json_recovery_messages(messages)

        assert recovery_messages[0]["role"] == "system"
        assert [message["role"] for message in recovery_messages[1:]] == ["user", "user"]
        assert "Return ONLY valid JSON" in recovery_messages[-1]["content"]


# ═══════════════════════════════════════════════════════════════════════
# Translation service orchestration tests (mocked)
# ═══════════════════════════════════════════════════════════════════════


class TestTranslateOptions:
    """TranslateOptions defaults and serialization."""

    def test_defaults(self):
        opts = TranslateOptions()
        assert opts.enable_thinking is False
        assert opts.force_overwrite_draft is False
        assert opts.retry_missing_only is True

    def test_with_provider_override(self):
        opts = TranslateOptions(
            target_language="fr",
            provider_override=ProviderOverride(
                provider_mode="openai_official",
                base_url="http://localhost:8033/v1",
                api_key=SecretStr("test-placeholder-key"),
            ),
        )
        assert opts.provider_override is not None
        assert opts.provider_override.provider_mode == "openai_official"

    def test_serialization_roundtrip(self):
        opts = TranslateOptions(target_language="ja", story_context="test")
        data = opts.model_dump(mode="json")
        restored = TranslateOptions.model_validate(data)
        assert restored.target_language == "ja"


# ═══════════════════════════════════════════════════════════════════════
# Language resolution tests
# ═══════════════════════════════════════════════════════════════════════


class TestLanguageResolution:
    """_resolve_target_language from job_dispatcher."""

    def test_request_language_wins(self):
        from app.services.job_dispatcher import _resolve_target_language

        options = TranslateOptions(target_language="fr")
        page = MagicMock()
        page.chapter = None

        result = _resolve_target_language(options, page)
        assert result == "fr"

    def test_project_fallback(self):
        from app.services.job_dispatcher import _resolve_target_language

        options = TranslateOptions(target_language=None)
        page = MagicMock()
        page.chapter.project.target_language = "de"

        result = _resolve_target_language(options, page)
        assert result == "de"

    def test_no_language_raises(self):
        from app.services.job_dispatcher import _resolve_target_language

        options = TranslateOptions(target_language=None)
        page = MagicMock()
        page.chapter = None

        with pytest.raises(TranslationLanguageResolutionError):
            _resolve_target_language(options, page)


# ═══════════════════════════════════════════════════════════════════════
# Status transition tests (Packet 6)
# ═══════════════════════════════════════════════════════════════════════


class TestStatusTransitions:
    """translation_status transitions respect the no-downgrade rule."""

    def test_draft_to_draft_generated(self):
        from app.services.translation_service import _STATUS_DRAFT_GENERATED, _NO_DOWNGRADE_STATUSES

        status = "draft"
        if status not in _NO_DOWNGRADE_STATUSES:
            status = _STATUS_DRAFT_GENERATED
        assert status == "draft_generated"

    def test_reviewed_not_downgraded(self):
        from app.services.translation_service import _STATUS_DRAFT_GENERATED, _NO_DOWNGRADE_STATUSES

        status = "reviewed"
        if status not in _NO_DOWNGRADE_STATUSES:
            status = _STATUS_DRAFT_GENERATED
        assert status == "reviewed"  # Should NOT change

    def test_finalized_not_downgraded(self):
        from app.services.translation_service import _STATUS_DRAFT_GENERATED, _NO_DOWNGRADE_STATUSES

        status = "finalized"
        if status not in _NO_DOWNGRADE_STATUSES:
            status = _STATUS_DRAFT_GENERATED
        assert status == "finalized"  # Should NOT change
