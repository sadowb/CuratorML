from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Project(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source_language: Mapped[str] = mapped_column(String(100), nullable=False)
    target_language: Mapped[str] = mapped_column(String(100), nullable=False)
    reading_direction: Mapped[str] = mapped_column(String(10), nullable=False)
    project_status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="active")
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    enable_ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    require_qc: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    user: Mapped["User | None"] = relationship("User", back_populates="projects")
    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    files: Mapped[list["ProjectFile"]] = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    memory_entries: Mapped[list["TranslationMemoryEntry"]] = relationship(
        "TranslationMemoryEntry",
        cascade="all, delete-orphan",
    )
