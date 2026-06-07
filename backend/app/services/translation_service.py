"""Translation orchestration service — Packet 5 + 6.

Performs the full translation flow for a single page:

1. Load active text regions sorted by reading order.
2. Build ``order → region_id`` mapping.
3. Apply OCR fallback chain (corrected → raw → exclude).
4. Generate helper image via ``PageHelperImageService``.
5. Build prompt (pure function).
6. Call gateway.
7. Persist mapped lines with overwrite/protection guards.
8. Return metrics dict.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

from app.core.config import settings
from app.models.page import Page
from app.repositories.page_repository import PageRepository
from app.schemas.translation import LLMTranslationLine, LLMTranslationResponse, TranslateOptions
from app.services.page_helper_image_service import PageHelperImageService
from app.services.translation_errors import (
    TranslationNoTextLinesError,
    TranslationOrderMappingError,
    TranslationPersistenceError,
)
from app.services.translation_gateway import TranslationGateway
from app.services.translation_memory_service import TranslationMemoryService
from app.services.translation_prompt import build_translation_prompt

logger = logging.getLogger("manga_api.translation_service")

# Translation status constants (Packet 6 state machine).
_STATUS_DRAFT = "draft"
_STATUS_DRAFT_GENERATED = "draft_generated"
_STATUS_REVIEWED = "reviewed"
_STATUS_FINALIZED = "finalized"
_NO_DOWNGRADE_STATUSES = frozenset({_STATUS_REVIEWED, _STATUS_FINALIZED})


@dataclass(slots=True)
class TranslationInputPlan:
    ordered_lines: list[dict[str, Any]] = field(default_factory=list)
    context_lines: list[dict[str, Any]] = field(default_factory=list)
    manual_protected_orders: list[int] = field(default_factory=list)
    excluded_no_source_orders: list[int] = field(default_factory=list)
    order_to_region: dict[int, uuid.UUID] = field(default_factory=dict)


def resolve_ocr_source(page_text: Any) -> str:
    return (
        (getattr(page_text, "ocr_text_corrected", None) or "").strip()
        or (getattr(page_text, "ocr_text_raw", None) or "").strip()
    )


def has_non_empty_manual_translation(page_text: Any) -> bool:
    return bool(
        (getattr(page_text, "display_text_final", None) or "").strip()
        or (getattr(page_text, "translation_corrected", None) or "").strip()
    )


def build_translation_inputs(
    sorted_regions: list[Any],
    text_by_region: dict[uuid.UUID, Any],
) -> TranslationInputPlan:
    plan = TranslationInputPlan()
    for order_idx, region in enumerate(sorted_regions, start=1):
        page_text = text_by_region.get(region.id)
        if page_text is None:
            plan.excluded_no_source_orders.append(order_idx)
            continue

        source_text = resolve_ocr_source(page_text)
        if not source_text:
            plan.excluded_no_source_orders.append(order_idx)
            continue

        line = {"order": order_idx, "text": source_text}
        plan.context_lines.append(line)

        if has_non_empty_manual_translation(page_text):
            plan.manual_protected_orders.append(order_idx)
            continue

        plan.order_to_region[order_idx] = region.id
        plan.ordered_lines.append(line)

    return plan


class TranslationService:
    """Orchestrates the translation pipeline for a single page."""

    def __init__(
        self,
        page_repo: PageRepository | None = None,
        helper_image_service: PageHelperImageService | None = None,
        translation_memory_service: TranslationMemoryService | None = None,
    ) -> None:
        self.page_repo = page_repo or PageRepository()
        self.helper_image_service = helper_image_service or PageHelperImageService(
            page_repo=self.page_repo,
        )
        self.translation_memory_service = translation_memory_service or TranslationMemoryService()

    async def run_for_page(
        self,
        db: AsyncSession,
        *,
        page: Page,
        pipeline_run_id: uuid.UUID,
        options: TranslateOptions,
        effective_target_language: str,
    ) -> dict[str, Any]:
        """Execute full translation flow and return metrics.

        Parameters
        ----------
        db
            Active async session (caller manages commit).
        page
            Page with eagerly-loaded relationships.
        pipeline_run_id
            The owning ``PipelineRun.id``.
        options
            Validated translate options from ``input_params_json``.
        effective_target_language
            Already-resolved BCP-47 target language.
        """
        # ── 1. Load active text regions ────────────────────────────
        all_regions = await self.page_repo.get_active_regions(
            db, page.id, kinds=["panel", "balloon", "text"],
        )
        region_map = {r.id: r for r in all_regions}
        text_regions = [r for r in all_regions if r.region_kind == "text"]
        region_ids = [r.id for r in text_regions]
        texts = await self.page_repo.get_texts_for_region_ids(db, region_ids)
        text_by_region: dict[uuid.UUID, Any] = {t.region_id: t for t in texts}

        def region_center(region) -> tuple[float, float]:
            bbox = region.bbox_json
            if isinstance(bbox, list) and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                try:
                    return (float(x1) + float(x2)) / 2.0, (float(y1) + float(y2)) / 2.0
                except Exception:
                    return 0.0, 0.0
            return 0.0, 0.0

        def get_sort_key(region) -> tuple:
            item_order = region.reading_order or 0
            bubble_order = 0
            panel_order = 0
            
            parent = region_map.get(region.parent_region_id) if region.parent_region_id else None
            if parent and parent.region_kind == "balloon":
                bubble_order = parent.reading_order or 0
                parent = region_map.get(parent.parent_region_id) if parent.parent_region_id else None
                
            if parent and parent.region_kind == "panel":
                panel_order = parent.reading_order or 0

            x, y = region_center(region)
            page_text = text_by_region.get(region.id)
            text_created_at = getattr(page_text, "created_at", None) if page_text is not None else None
            text_id = str(getattr(page_text, "id", "")) if page_text is not None else ""

            return (
                panel_order == 0, panel_order,
                bubble_order == 0, bubble_order,
                item_order == 0, item_order,
                x, y,
                text_created_at is None, text_created_at,
                text_id,
                str(region.id)
            )

        sorted_regions = sorted(text_regions, key=get_sort_key)

        # ── 2. Build order → region_id mapping + OCR context ───────
        input_plan = build_translation_inputs(sorted_regions, text_by_region)
        order_to_region = input_plan.order_to_region
        ordered_lines = input_plan.ordered_lines
        context_lines = input_plan.context_lines
        excluded_no_source = input_plan.excluded_no_source_orders

        if options.retry_missing_only and not options.force_overwrite_draft:
            skipped_existing_draft_orders: list[int] = []
            filtered_lines: list[dict[str, Any]] = []
            filtered_order_to_region: dict[int, uuid.UUID] = {}
            for line in ordered_lines:
                order = int(line["order"])
                region_id = order_to_region[order]
                page_text = text_by_region.get(region_id)
                if page_text is not None and (page_text.translation_draft or "").strip():
                    skipped_existing_draft_orders.append(order)
                    continue
                filtered_lines.append(line)
                filtered_order_to_region[order] = region_id
            ordered_lines = filtered_lines
            order_to_region = filtered_order_to_region
        else:
            skipped_existing_draft_orders = []

        if not ordered_lines:
            # No-op: nothing to translate
            return {
                "effective_target_language": effective_target_language,
                "requested_orders": 0,
                "translated_orders": 0,
                "missing_orders": 0,
                "invalid_orders": 0,
                "excluded_no_source_text_orders": excluded_no_source,
                "manual_protected_orders": input_plan.manual_protected_orders,
                "skipped_existing_draft_orders": skipped_existing_draft_orders,
                "context_orders": [line["order"] for line in context_lines],
                "processed_regions": 0,
                "failed_regions": 0,
                "provider_mode": _resolve_provider_mode(options),
                "base_url_used": _resolve_base_url(options),
                "model": _resolve_model(options),
                "latency_ms": 0,
                "retry_count": 0,
                "enable_thinking_requested": options.enable_thinking,
                "force_overwrite_draft": options.force_overwrite_draft,
                "retry_missing_only": options.retry_missing_only,
            }

        provider_mode = _resolve_provider_mode(options)

        # ── 3. Generate helper image ──────────────────────────────
        helper_image_failed = False
        memory_retrieval_failed = False
        helper_b64: str | None = None
        helper_mime = "image/png"
        try:
            helper_result = await self.helper_image_service.generate_grounded_helper(
                db,
                page=page,
                pipeline_run_id=pipeline_run_id,
                persist_debug=True,
            )
            prepared_bytes, prepared_mime = _prepare_helper_image_for_prompt(
                helper_result.image_bytes,
                helper_result.mime_type,
                provider_mode=provider_mode,
            )
            helper_b64 = base64.b64encode(prepared_bytes).decode("ascii")
            helper_mime = prepared_mime
        except Exception:
            helper_image_failed = True
            logger.warning(
                "Helper image generation failed for page %s, proceeding without",
                page.id,
                exc_info=True,
            )

        # ── 4. Build prompt ──────────────────────────────────────
        memory_block: dict[str, Any] | None = None
        try:
            chapter_number = (
                page.chapter.chapter_number
                if page.chapter is not None
                else None
            )
            project_id = (
                page.chapter.project_id
                if page.chapter is not None
                else None
            )
            if project_id is not None:
                memory_block = await self.translation_memory_service.retrieve_for_page(
                    db,
                    project_id=project_id,
                    scope_chapter=chapter_number,
                    ocr_lines=[line["text"] for line in ordered_lines],
                    story_context=options.story_context,
                )
        except Exception:
            memory_retrieval_failed = True
            logger.warning(
                "Translator memory retrieval failed for page %s, proceeding without memory block",
                page.id,
                exc_info=True,
            )

        # ── 5. Call gateway (all lines + missing-order recovery loop) ───
        gateway = _build_gateway(options)
        line_by_order: dict[int, LLMTranslationLine] = {}
        expected_orders = set(order_to_region.keys())
        page_summary: str | None = None

        gateway_calls = 0
        gateway_latency_ms_total = 0
        gateway_retry_count_total = 0
        gateway_json_recovery_retry_count_total = 0
        max_output_tokens_effective: int | None = None

        trace_events: list[dict[str, Any]] = []

        messages = build_translation_prompt(
            ordered_lines=ordered_lines,
            context_lines=context_lines,
            target_language=effective_target_language,
            story_context=options.story_context,
            memory_block=memory_block,
            helper_image_b64=helper_b64,
            helper_image_mime=helper_mime,
            enable_thinking=options.enable_thinking,
        )
        response, metrics = await gateway.translate(
            messages,
            enable_thinking=options.enable_thinking,
        )
        trace_events.append(
            {
                "event": "full_page_response",
                "orders": [line["order"] for line in ordered_lines],
                "context_orders": [line["order"] for line in context_lines],
                "story_context_present": bool((options.story_context or "").strip()),
                "story_context": options.story_context,
                "request_messages": _sanitize_messages_for_trace(messages),
                "response_raw_text": metrics.get("raw_response_text"),
                "response_parsed": (
                    response.model_dump()
                    if hasattr(response, "model_dump")
                    else str(response)
                ),
                "metrics": metrics,
            }
        )
        gateway_calls += 1
        gateway_latency_ms_total += int(metrics.get("latency_ms", 0) or 0)
        gateway_retry_count_total += int(metrics.get("retry_count", 0) or 0)
        gateway_json_recovery_retry_count_total += int(
            metrics.get("json_recovery_retry_count", 0) or 0
        )
        if metrics.get("max_output_tokens_effective") is not None:
            max_output_tokens_effective = int(metrics["max_output_tokens_effective"])

        if response.page_summary:
            page_summary = response.page_summary

        for line in response.lines:
            if line.order in expected_orders and line.order not in line_by_order:
                line_by_order[line.order] = line

        # Recovery pass loop for orders the model skipped.
        missing_orders_list = sorted(expected_orders - set(line_by_order.keys()))
        missing_recovery_attempted = bool(missing_orders_list)
        missing_recovery_recovered = 0
        recovery_loops = 0

        while missing_orders_list and recovery_loops < 3:
            recovery_loops += 1
            retry_lines = [line for line in ordered_lines if line["order"] in set(missing_orders_list)]
            retry_messages = build_translation_prompt(
                ordered_lines=retry_lines,
                context_lines=context_lines,
                target_language=effective_target_language,
                story_context=options.story_context,
                memory_block=memory_block,
                helper_image_b64=helper_b64,
                helper_image_mime=helper_mime,
                enable_thinking=options.enable_thinking,
            )
            retry_response, retry_metrics = await gateway.translate(
                retry_messages,
                enable_thinking=options.enable_thinking,
            )
            trace_events.append(
                {
                    "event": f"retry_missing_orders_response_loop_{recovery_loops}",
                    "missing_orders_requested": missing_orders_list,
                    "context_orders": [line["order"] for line in context_lines],
                    "story_context_present": bool((options.story_context or "").strip()),
                    "story_context": options.story_context,
                    "request_messages": _sanitize_messages_for_trace(retry_messages),
                    "response_raw_text": retry_metrics.get("raw_response_text"),
                    "response_parsed": (
                        retry_response.model_dump()
                        if hasattr(retry_response, "model_dump")
                        else str(retry_response)
                    ),
                    "metrics": retry_metrics,
                }
            )
            gateway_calls += 1
            gateway_latency_ms_total += int(retry_metrics.get("latency_ms", 0) or 0)
            gateway_retry_count_total += int(retry_metrics.get("retry_count", 0) or 0)
            gateway_json_recovery_retry_count_total += int(
                retry_metrics.get("json_recovery_retry_count", 0) or 0
            )
            if retry_metrics.get("max_output_tokens_effective") is not None:
                max_output_tokens_effective = max(
                    max_output_tokens_effective or 0,
                    int(retry_metrics["max_output_tokens_effective"])
                )

            if page_summary is None and retry_response.page_summary:
                page_summary = retry_response.page_summary

            missing_set = set(missing_orders_list)
            for line in retry_response.lines:
                if line.order in missing_set and line.order not in line_by_order:
                    line_by_order[line.order] = line
                    missing_recovery_recovered += 1
            
            missing_orders_list = sorted(expected_orders - set(line_by_order.keys()))

        # ── 6. Map + persist results ─────────────────────────────
        translated_orders: list[int] = []
        missing_orders: list[int] = []
        invalid_orders: list[int] = []
        processed_regions = 0
        failed_regions = 0

        for order, region_id in order_to_region.items():
            llm_line = line_by_order.get(order)
            if llm_line is None:
                missing_orders.append(order)
                continue

            page_text = text_by_region.get(region_id)
            if page_text is None:
                invalid_orders.append(order)
                failed_regions += 1
                continue

            try:
                # Protection: never touch corrected/final
                # Overwrite guard
                if not options.force_overwrite_draft and (page_text.translation_draft or "").strip():
                    # Already has a draft, skip
                    continue

                page_text.pipeline_run_id = pipeline_run_id
                page_text.translation_draft = llm_line.natural_translation
                page_text.context_notes = llm_line.speaker_context or llm_line.image_explanation

                # Status transition (Packet 6)
                if page_text.translation_status not in _NO_DOWNGRADE_STATUSES:
                    page_text.translation_status = _STATUS_DRAFT_GENERATED

                translated_orders.append(order)
                processed_regions += 1
            except Exception:
                logger.exception("Failed to persist translation for region %s", region_id)
                failed_regions += 1

        # Check for extra orders from LLM (not in our mapping)
        expected = set(order_to_region.keys())
        received = set(line_by_order.keys())
        extra = received - expected
        if extra:
            invalid_orders.extend(sorted(extra))

        # ── 7. Build metrics ─────────────────────────────────────
        metrics: dict[str, Any] = {
            "effective_target_language": effective_target_language,
            "requested_orders": len(ordered_lines),
            "translated_orders": len(translated_orders),
            "missing_orders": sorted(missing_orders_list),
            "invalid_orders": sorted(invalid_orders),
            "excluded_no_source_text_orders": sorted(excluded_no_source),
            "manual_protected_orders": sorted(input_plan.manual_protected_orders),
            "skipped_existing_draft_orders": sorted(skipped_existing_draft_orders),
            "context_orders": [line["order"] for line in context_lines],
            "processed_regions": processed_regions,
            "failed_regions": failed_regions,
            "provider_mode": provider_mode,
            "base_url_used": _resolve_base_url(options),
            "model": _resolve_model(options),
                "enable_thinking_requested": options.enable_thinking,
                "force_overwrite_draft": options.force_overwrite_draft,
                "retry_missing_only": options.retry_missing_only,
                "memory_stats": (
                    memory_block.get("stats")
                    if isinstance(memory_block, dict)
                    else None
                ),
                "gateway_calls": gateway_calls,
                "gateway_latency_ms_total": gateway_latency_ms_total,
                "gateway_retry_count_total": gateway_retry_count_total,
                "gateway_json_recovery_retry_count_total": gateway_json_recovery_retry_count_total,
                "max_output_tokens_effective": max_output_tokens_effective,
                "chunk_size": len(ordered_lines),
                "chunk_count": 1,
                "missing_recovery_attempted": missing_recovery_attempted,
                "missing_recovery_recovered": missing_recovery_recovered,
                "helper_image_failed": helper_image_failed,
                "memory_retrieval_failed": memory_retrieval_failed,
            }

        # Store page_summary in metrics if present
        if page_summary:
            metrics["page_summary"] = page_summary

        _write_llm_trace_snapshot(
            {
                "page_id": str(page.id),
                "pipeline_run_id": str(pipeline_run_id),
                "target_language": effective_target_language,
                "story_context_present": bool((options.story_context or "").strip()),
                "story_context": options.story_context,
                "provider_mode": provider_mode,
                "model": _resolve_model(options),
                "chunk_count": 1,
                "trace_events": trace_events,
                "run_metrics": metrics,
            }
        )

        return metrics


# ── Module-level helpers ──────────────────────────────────────────────




def _build_gateway(options: TranslateOptions) -> TranslationGateway:
    """Construct a ``TranslationGateway`` from run options + config defaults."""
    override = options.provider_override
    provider_mode = _resolve_provider_mode(options)
    timeout = settings.translation_timeout_seconds
    max_retries = settings.translation_max_retries
    use_streaming = False

    # Local OpenAI-compatible servers can legitimately need much longer than
    # hosted APIs for a single completion. Retrying a timed-out long generation
    # from scratch is usually counterproductive.
    if provider_mode == "compatible_local":
        timeout = max(timeout, settings.translation_local_timeout_seconds)
        max_retries = 1
        # For strict JSON workflows, prefer full non-streaming responses so we
        # parse one complete payload instead of assembling streamed fragments.
        use_streaming = False

    return TranslationGateway(
        base_url=override.base_url if override else None,
        api_key=override.api_key.get_secret_value() if override and override.api_key else None,
        model=options.model,
        max_output_tokens=options.max_output_tokens,
        timeout=timeout,
        max_retries=max_retries,
        use_streaming=use_streaming,
        local_compat_mode=(provider_mode == "compatible_local"),
    )


def _resolve_provider_mode(options: TranslateOptions) -> str:
    if options.provider_override:
        return options.provider_override.provider_mode
    return settings.translation_provider_mode


def _resolve_base_url(options: TranslateOptions) -> str:
    if options.provider_override and options.provider_override.base_url:
        return options.provider_override.base_url
    return settings.translation_base_url


def _resolve_model(options: TranslateOptions) -> str:
    return options.model or settings.translation_model


def _prepare_helper_image_for_prompt(
    image_bytes: bytes,
    mime_type: str,
    *,
    provider_mode: str,
) -> tuple[bytes, str]:
    """Prepare helper image payload for multimodal prompt.

    For local compatible providers, downscale + JPEG-compress to keep
    request payload manageable while preserving visual grounding.
    """
    if provider_mode != "compatible_local":
        return image_bytes, mime_type

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        max_dim = 1024
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        quality = 80
        img.save(output, format="JPEG", quality=quality, optimize=True)
        data = output.getvalue()

        # Keep payload around <= 400KB when possible.
        while len(data) > 400_000 and quality > 45:
            quality -= 10
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            data = output.getvalue()

        return data, "image/jpeg"
    except Exception:
        # If processing fails, fall back to original bytes.
        logger.warning("Failed to optimize helper image payload", exc_info=True)
        return image_bytes, mime_type


def _sanitize_messages_for_trace(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize messages to keep trace readable (strip huge base64 blobs)."""
    sanitized: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", ""))
        content = message.get("content")

        if isinstance(content, list):
            blocks: list[dict[str, Any]] = []
            for block in content:
                if not isinstance(block, dict):
                    blocks.append({"type": "unknown", "value": str(block)})
                    continue

                block_type = str(block.get("type", ""))
                if block_type == "image_url":
                    image_url = block.get("image_url")
                    if isinstance(image_url, dict):
                        url = str(image_url.get("url", ""))
                    else:
                        url = str(image_url or "")
                    blocks.append(
                        {
                            "type": "image_url",
                            "image_url": _summarize_data_url(url),
                        }
                    )
                elif block_type == "text":
                    blocks.append(
                        {
                            "type": "text",
                            "text": str(block.get("text", "")),
                        }
                    )
                else:
                    blocks.append(
                        {
                            "type": block_type or "unknown",
                            "value": str(block),
                        }
                    )
            sanitized.append({"role": role, "content": blocks})
        else:
            sanitized.append({"role": role, "content": str(content or "")})
    return sanitized


def _summarize_data_url(data_url: str) -> dict[str, Any]:
    if not data_url.startswith("data:"):
        return {"kind": "url", "value": data_url}
    if ";base64," not in data_url:
        return {"kind": "data_url", "value": data_url}
    header, payload = data_url.split(";base64,", 1)
    mime = header.removeprefix("data:")
    return {
        "kind": "data_url_base64",
        "mime": mime,
        "base64_chars": len(payload),
    }


def _write_llm_trace_snapshot(trace_payload: dict[str, Any]) -> None:
    """Write latest run trace (overwrite previous)."""
    try:
        log_dir = settings.storage_root_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "translation_llm_trace.jsonl"
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **trace_payload,
        }
        with path.open("w", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False, default=str))
            file.write("\n")
    except Exception:
        logger.warning("Failed to write translation LLM trace snapshot", exc_info=True)
