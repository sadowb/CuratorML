from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - fallback for environments without pgvector pkg.
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):  # type: ignore[override]
        cache_ok = True

        def __init__(self, dimension: int) -> None:
            self.dimension = dimension

        def get_col_spec(self, **_: Any) -> str:
            return f"vector({self.dimension})"


class TranslationMemoryEntry(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "translation_memory_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('character', 'attack', 'place', 'organization')",
            name="translation_memory_entry_type_check",
        ),
        CheckConstraint(
            "scope_chapter IS NULL OR scope_chapter >= 1",
            name="translation_memory_scope_chapter_check",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_term: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_translation: Mapped[str] = mapped_column(Text, nullable=False)
    scope_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_source_term: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)
    search_document: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
