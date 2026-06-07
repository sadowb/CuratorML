from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class PageRegion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "page_regions"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("page_regions.id"), nullable=True, index=True)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    region_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    polygon_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bbox_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    reading_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    page: Mapped["Page"] = relationship("Page", back_populates="regions")
    pipeline_run: Mapped["PipelineRun | None"] = relationship("PipelineRun", back_populates="page_regions")
    parent_region: Mapped["PageRegion | None"] = relationship("PageRegion", remote_side="PageRegion.id")
    texts: Mapped[list["PageText"]] = relationship("PageText", back_populates="region", cascade="all, delete-orphan")
