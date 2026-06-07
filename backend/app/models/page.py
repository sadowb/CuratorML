from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Page(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pages"

    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, server_default="uploaded")
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")

    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="pages")
    files: Mapped[list["PageFile"]] = relationship("PageFile", back_populates="page", cascade="all, delete-orphan")
    regions: Mapped[list["PageRegion"]] = relationship("PageRegion", back_populates="page", cascade="all, delete-orphan")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship("PipelineRun", back_populates="page", cascade="all, delete-orphan")
