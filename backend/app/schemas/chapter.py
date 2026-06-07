from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChapterCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    chapter_number: int = Field(ge=1)


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    chapter_number: int
    chapter_status: str
    created_at: datetime
    updated_at: datetime
