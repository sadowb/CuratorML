from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chapter import ChapterOut


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    source_language: str = Field(min_length=2, max_length=100)
    target_language: str = Field(min_length=2, max_length=100)
    reading_direction: str = Field(pattern="^(LTR|RTL)$")
    chapter_title: str = Field(min_length=1, max_length=255)
    chapter_number: int = Field(ge=1)
    estimated_pages: int | None = Field(default=None, ge=1)
    context: str | None = None
    enable_ocr: bool = True
    require_qc: bool = True


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    source_language: str
    target_language: str
    reading_direction: str
    project_status: str
    context: str | None
    enable_ocr: bool
    require_qc: bool
    created_at: datetime
    updated_at: datetime


class ProjectListItem(ProjectOut):
    chapter_count: int = 0
    page_count: int = 0


class ProjectWithChaptersOut(BaseModel):
    project: ProjectOut
    chapters: list[ChapterOut]


class ProjectCreateResponse(BaseModel):
    project: ProjectOut
    chapter: ChapterOut


class ProjectEntryOut(BaseModel):
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None
    page_id: uuid.UUID | None
    editor_url: str | None
    upload_url: str | None
    reason: str
