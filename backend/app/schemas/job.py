"""Pydantic schemas for the job / pipeline-run API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.translation import TranslateOptions


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class InpaintOptions(BaseModel):
    """Options for ``stage='inpaint'`` jobs."""

    method: Literal["telea", "ns"] = "telea"
    radius: float = Field(default=5.0, ge=1.0, le=20.0)
    ai_expand_strength: float = Field(default=0.2, ge=0.0, le=1.0)
    text_expand_px: float = Field(default=0.0, ge=0.0, le=40.0)
    balloon_safe_inset_mode: Literal["auto", "manual"] = "auto"
    balloon_safe_inset_px: float | None = Field(default=None, ge=0.0, le=64.0)
    clip_fallback_mode: Literal["no_clip", "inset_bbox"] = "no_clip"


class JobSubmitRequest(BaseModel):
    """Body for submitting a new pipeline job."""

    stage: Literal[
        "mask_inference",
        "ocr",
        "inpaint",
        "helper_grounded",
        "reading_order",
        "translate",
        "render_preview",
    ]
    translate_options: TranslateOptions | None = None
    inpaint_options: InpaintOptions | None = None
    force: bool = Field(
        default=False, 
        description="If true, cancels existing pending/running runs for this stage."
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_inpaint_payload(cls, value: object) -> object:
        """Back-compat: promote flat inpaint keys into inpaint_options.

        Older UI payloads could send:
          {"stage":"inpaint","method":"ns","radius":8,...}
        instead of nesting under ``inpaint_options``.
        """
        if not isinstance(value, dict):
            return value
        if value.get("stage") != "inpaint":
            return value
        if value.get("inpaint_options") is not None:
            return value

        keys = (
            "method",
            "radius",
            "ai_expand_strength",
            "text_expand_px",
            "balloon_safe_inset_mode",
            "balloon_safe_inset_px",
            "clip_fallback_mode",
        )
        promoted = {key: value[key] for key in keys if key in value and value[key] is not None}
        if not promoted:
            return value

        normalized = dict(value)
        normalized["inpaint_options"] = promoted
        return normalized

    @model_validator(mode="after")
    def validate_stage_options(self) -> "JobSubmitRequest":
        if self.stage == "translate" and self.translate_options is None:
            raise ValueError("translate_options is required when stage is 'translate'")
        if self.stage != "translate" and self.translate_options is not None:
            raise ValueError("translate_options must not be provided for non-translate stages")
        if self.stage == "inpaint" and self.inpaint_options is None:
            raise ValueError("inpaint_options is required when stage is 'inpaint'")
        if self.stage != "inpaint" and self.inpaint_options is not None:
            raise ValueError("inpaint_options must not be provided for non-inpaint stages")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class JobSubmitResponse(BaseModel):
    """Returned immediately (202) after a job is accepted."""

    job_id: uuid.UUID
    page_id: uuid.UUID
    stage: str
    status: str  # "pending"

    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    """Full job status snapshot."""

    job_id: uuid.UUID
    page_id: uuid.UUID
    stage: str
    status: str
    model_name: str | None = None
    error_message: str | None = None
    metrics_json: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class JobSSEEvent(BaseModel):
    """Payload sent over the SSE stream for real-time updates."""

    job_id: str
    status: str
    detail: str | None = None
    payload: dict[str, Any] | None = None
