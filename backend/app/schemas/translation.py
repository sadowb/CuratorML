"""Pydantic schemas for the translation pipeline.

Contains:
  * LLM response contract (``LLMTranslationLine``, ``LLMTranslationResponse``)
  * Request-side translate options (``ProviderOverride``, ``TranslateOptions``)
"""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr, field_validator


# ---------------------------------------------------------------------------
# LLM response contract (Packet 3)
# ---------------------------------------------------------------------------

class LLMTranslationLine(BaseModel):
    """One translated line as returned by the model.

    ``order`` corresponds to the 1-based reading-order index sent in the
    prompt.  ``source_text`` is echoed for QA/audit — it is **not**
    persisted into ``PageText`` but may be included in metrics.
    """

    order: int = Field(..., ge=1)
    source_text: str
    literal_translation: str
    natural_translation: str
    speaker_context: str | None = None
    image_explanation: str | None = None


class LLMTranslationResponse(BaseModel):
    """Top-level JSON contract expected from the LLM."""

    page_summary: str | None = None
    lines: list[LLMTranslationLine]

    @field_validator("lines")
    @classmethod
    def deduplicate_orders(cls, lines: list[LLMTranslationLine]) -> list[LLMTranslationLine]:
        """Keep first occurrence of each ``order`` value — extras are dropped."""
        seen: set[int] = set()
        unique: list[LLMTranslationLine] = []
        for line in lines:
            if line.order not in seen:
                seen.add(line.order)
                unique.append(line)
        return unique


# ---------------------------------------------------------------------------
# Request-side translate options (Packet 2)
# ---------------------------------------------------------------------------

class ProviderOverride(BaseModel):
    """Per-run override for the translation provider."""

    provider_mode: str = "compatible_local"  # or "openai_official"
    base_url: str | None = None
    api_key: SecretStr | None = None


class TranslateOptions(BaseModel):
    """Options sent alongside ``stage='translate'`` in ``JobSubmitRequest``."""

    target_language: str | None = None
    story_context: str | None = None
    model: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=128, le=8192)
    enable_thinking: bool = False
    force_overwrite_draft: bool = False
    retry_missing_only: bool = True
    provider_override: ProviderOverride | None = None
