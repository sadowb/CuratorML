from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Chapter(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapters"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="active")

    project: Mapped["Project"] = relationship("Project", back_populates="chapters")
    files: Mapped[list["ChapterFile"]] = relationship("ChapterFile", back_populates="chapter", cascade="all, delete-orphan")
    pages: Mapped[list["Page"]] = relationship("Page", back_populates="chapter", cascade="all, delete-orphan")
