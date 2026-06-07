from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntryType = Literal["character", "attack", "place", "organization"]


class MemoryEntryCreate(BaseModel):
    entry_type: EntryType
    source_term: str = Field(min_length=1)
    preferred_translation: str = Field(min_length=1)
    scope_chapter: int | None = Field(default=None, ge=1)
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("aliases")
    @classmethod
    def strip_aliases(cls, aliases: list[str]) -> list[str]:
        cleaned = [(alias or "").strip() for alias in aliases]
        return [alias for alias in cleaned if alias]


class MemoryEntryUpdate(BaseModel):
    entry_type: EntryType | None = None
    source_term: str | None = Field(default=None, min_length=1)
    preferred_translation: str | None = Field(default=None, min_length=1)
    scope_chapter: int | None = Field(default=None, ge=1)
    aliases: list[str] | None = None
    notes: str | None = None

    @field_validator("aliases")
    @classmethod
    def strip_aliases(cls, aliases: list[str] | None) -> list[str] | None:
        if aliases is None:
            return None
        cleaned = [(alias or "").strip() for alias in aliases]
        return [alias for alias in cleaned if alias]


class MemoryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    entry_type: EntryType
    source_term: str
    preferred_translation: str
    scope_chapter: int | None
    aliases: list[str]
    notes: str | None
    created_at: datetime
    updated_at: datetime


class MemoryEntryBatchCreate(BaseModel):
    entries: list[MemoryEntryCreate] = Field(default_factory=list, min_length=1)


class MemoryEntryBatchFailure(BaseModel):
    index: int
    source_term: str
    detail: str


class MemoryEntryBatchOut(BaseModel):
    created: list[MemoryEntryOut]
    failed: list[MemoryEntryBatchFailure]
