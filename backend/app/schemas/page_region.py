from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PageRegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    parent_region_id: uuid.UUID | None
    pipeline_run_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    region_kind: str
    polygon_json: list[list[float]] | None
    bbox_json: list[float] | None = Field(default=None, min_length=4, max_length=4)
    confidence: float | None
    reading_order: int | None
    origin: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PageRegionCreateRequest(BaseModel):
    region_kind: str
    polygon_json: list[list[float]] | None = None
    bbox_json: list[float] | None = Field(default=None, min_length=4, max_length=4)
    confidence: float | None = 1.0
    reading_order: int | None = None
    parent_region_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def ensure_geometry(self) -> "PageRegionCreateRequest":
        if self.polygon_json is None and self.bbox_json is None:
            raise ValueError("Either polygon_json or bbox_json must be provided")
        return self


class PageRegionPatchRequest(BaseModel):
    polygon_json: list[list[float]] | None = None
    bbox_json: list[float] | None = Field(default=None, min_length=4, max_length=4)
    region_kind: str | None = None
    confidence: float | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def ensure_at_least_one_field(self) -> "PageRegionPatchRequest":
        if all(
            value is None
            for value in [
                self.polygon_json,
                self.bbox_json,
                self.region_kind,
                self.confidence,
                self.is_active,
            ]
        ):
            raise ValueError("At least one field must be provided")
        return self
