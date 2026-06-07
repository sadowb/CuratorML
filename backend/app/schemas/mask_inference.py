from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class DetectionOut(BaseModel):
    id: int
    region_kind: str
    box: list[float] = Field(min_length=4, max_length=4)
    conf: float
    mask: list[list[float]]


class MaskInferenceResponse(BaseModel):
    pipeline_run_id: uuid.UUID
    page_id: uuid.UUID
    stage: str
    detections: list[DetectionOut]