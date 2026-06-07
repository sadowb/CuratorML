from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.page_region import PageRegionOut


class PageFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    pipeline_run_id: uuid.UUID | None
    file_kind: str
    file_path: str
    mime_type: str
    width: int | None
    height: int | None
    is_current: bool
    created_at: datetime
    url: str | None = None


class PageTextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    region_id: uuid.UUID
    pipeline_run_id: uuid.UUID | None
    ocr_text_raw: str | None
    ocr_text_corrected: str | None
    ocr_confidence: float | None
    context_notes: str | None
    translation_draft: str | None
    translation_corrected: str | None
    display_text_final: str | None
    render_scale: float | None = None
    render_color: str | None = None
    render_font_family: str | None = None
    render_font_weight: str | None = None
    render_bounds: list[float] | None = None
    translation_status: str
    created_at: datetime
    updated_at: datetime


class PageSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chapter_id: uuid.UUID
    page_number: int
    current_stage: str
    review_status: str
    created_at: datetime
    updated_at: datetime
    original_file_url: str | None = None


class PagePaginationOut(BaseModel):
    page: int
    page_size: int
    total: int
    has_next: bool
    has_prev: bool


class PaginatedPageSummaryOut(BaseModel):
    items: list[PageSummaryOut]
    pagination: PagePaginationOut


# For page detail, we include the associated files, texts, and regions
class PageDetailOut(PageSummaryOut):
    files: list[PageFileOut] = Field(default_factory=list)
    texts: list[PageTextOut] = Field(default_factory=list)
    regions: list[PageRegionOut] = Field(default_factory=list)


class PageUploadItemOut(BaseModel):
    page: PageSummaryOut
    file: PageFileOut


class PageUploadResponse(BaseModel):
    items: list[PageUploadItemOut]


class PageTextPatchRequest(BaseModel):
    ocr_text_corrected: str | None = None
    translation_corrected: str | None = None
    display_text_final: str | None = None
    translation_status: str | None = None
    context_notes: str | None = None
    render_scale: float | None = Field(default=None, ge=0.6, le=2.0)
    render_color: str | None = None
    render_font_family: str | None = None
    render_font_weight: str | None = None
    render_bounds: list[float] | None = Field(default=None, min_length=4, max_length=4)

    @model_validator(mode="after")
    def ensure_at_least_one_field(self) -> "PageTextPatchRequest":
        if len(self.model_fields_set) == 0:
            raise ValueError("At least one field must be provided")
        return self


class PageOcrTextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: uuid.UUID
    reading_order: int | None
    ocr_text_raw: str | None
    ocr_confidence: float | None
    


class PageOcrResultOut(BaseModel):
    page_id: uuid.UUID
    items: list[PageOcrTextOut] = Field(default_factory=list)


class ReadingOrderPanelOut(BaseModel):
    panel: PageRegionOut
    items: list[PageRegionOut] = Field(default_factory=list)


class PageReadingOrderOut(BaseModel):
    page_id: uuid.UUID
    panels: list[ReadingOrderPanelOut] = Field(default_factory=list)


class PageInpaintResultOut(BaseModel):
    page_id: uuid.UUID
    file: PageFileOut | None = None


class PageInpaintCleanupRequest(BaseModel):
    image_data_url: str = Field(min_length=1)


class PageInpaintCleanupOut(BaseModel):
    page_id: uuid.UUID
    file: PageFileOut


class PageTextReadItemOut(BaseModel):
    page_text_id: uuid.UUID | None
    region_id: uuid.UUID
    page_id: uuid.UUID
    reading_order: int | None
    ocr_text_raw: str | None
    ocr_text_corrected: str | None
    translation_draft: str | None


class PageTextsReadOut(BaseModel):
    page_id: uuid.UUID
    items: list[PageTextReadItemOut] = Field(default_factory=list)
