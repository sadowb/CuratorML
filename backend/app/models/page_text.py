from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class PageText(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "page_texts"

    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("page_regions.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True, index=True)
    ocr_text_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text_corrected: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True)
    context_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_corrected: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_text_final: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_scale: Mapped[float | None] = mapped_column(nullable=True)
    render_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    render_font_family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    render_font_weight: Mapped[str | None] = mapped_column(String(16), nullable=True)
    render_bounds: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    translation_status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="draft")

    region: Mapped["PageRegion"] = relationship("PageRegion", back_populates="texts")
    pipeline_run: Mapped["PipelineRun | None"] = relationship("PipelineRun", back_populates="page_texts")
