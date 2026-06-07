from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator


TextGroup = Literal["Dialogue", "Floating"]


class CanvasSize(BaseModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class PageImageAsset(BaseModel):
    file_id: uuid.UUID
    file_kind: str
    file_path: str
    mime_type: str
    width: int | None = None
    height: int | None = None


class RegionGeometry(BaseModel):
    id: uuid.UUID
    name: str
    region_kind: Literal["panel", "balloon", "text"]
    polygon: list[list[float]] | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    source_region_id: uuid.UUID


class TranslatedTextBlock(BaseModel):
    id: uuid.UUID
    name: str
    translated_text: str = ""
    ocr_text: str | None = None
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    panel_id: uuid.UUID | None = None
    balloon_id: uuid.UUID | None = None
    group: TextGroup
    font_size: float = Field(default=24.0, gt=0)
    font_name: str | None = None
    font_weight: Literal["normal", "bold"] = "normal"
    color: str = "#000000"
    visibility: bool = True
    region_id: uuid.UUID | None = None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("color must not be empty")
        if normalized.startswith("#") and len(normalized) in {4, 7, 9}:
            return normalized
        raise ValueError("color must be a hex string, for example '#000000'")


class PageExportOptions(BaseModel):
    include_preview: bool = False
    include_ocr_notes: bool = False
    include_brush_cleanup: bool = False
    include_merged_preview: bool = True
    original_visible: bool = True
    inpainted_visible: bool = True
    helper_layers_visible: bool = False


class PageExportDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: uuid.UUID
    page_id: uuid.UUID
    chapter_id: uuid.UUID
    project_id: uuid.UUID
    canvas: CanvasSize
    original_image: PageImageAsset
    inpainted_image: PageImageAsset | None = None
    preview_image: PageImageAsset | None = None
    brush_cleanup_image: PageImageAsset | None = None
    panel_masks: list[RegionGeometry] = Field(default_factory=list)
    balloon_masks: list[RegionGeometry] = Field(default_factory=list)
    text_masks: list[RegionGeometry] = Field(default_factory=list)
    translated_text_blocks: list[TranslatedTextBlock] = Field(default_factory=list)
    options: PageExportOptions = Field(default_factory=PageExportOptions)


@dataclass(slots=True)
class ResolvedRasterAsset:
    asset_key: str
    name: str
    kind: str
    rgba: np.ndarray
    source_kind: str
    source_ids: dict[str, str]
    fallback_used: bool = False


@dataclass(slots=True)
class ResolvedPageAssets:
    canvas: CanvasSize
    original: ResolvedRasterAsset
    inpainted: ResolvedRasterAsset
    panels: list[ResolvedRasterAsset]
    balloons: list[ResolvedRasterAsset]
    text_masks: list[ResolvedRasterAsset]
    dialogue_text_layers: list[ResolvedRasterAsset]
    floating_text_layers: list[ResolvedRasterAsset]
    helper_layers: list[ResolvedRasterAsset]
    preview: ResolvedRasterAsset | None
    merged_preview: ResolvedRasterAsset | None
    input_summary: dict[str, int]
    fallback_notes: list[str]


class PsdLayerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    z_index: int = Field(ge=0)
    layer_id: str
    name: str
    group_path: str
    visible: bool = True
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    blend_mode: str = "normal"
    source_kind: str
    source_ids: dict[str, str] = Field(default_factory=dict)
    fallback_used: bool = False
    asset_key: str


@dataclass(slots=True)
class PsdWriteSpec:
    export_id: uuid.UUID
    page_id: uuid.UUID
    created_at: datetime
    root_name: str
    canvas: CanvasSize
    group_order: list[str]
    layers: list[PsdLayerSpec]
    raster_assets: dict[str, np.ndarray]
    writer_name: str
    writer_version: str
    input_summary: dict[str, int]
    fallback_notes: list[str]
    text_layers: list[TranslatedTextBlock] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        *,
        export_id: uuid.UUID,
        page_id: uuid.UUID,
        root_name: str,
        canvas: CanvasSize,
        group_order: list[str],
        layers: list[PsdLayerSpec],
        text_layers: list[TranslatedTextBlock] = None,
        raster_assets: dict[str, np.ndarray],
        writer_name: str,
        writer_version: str,
        input_summary: dict[str, int],
        fallback_notes: list[str],
    ) -> "PsdWriteSpec":
        return cls(
            export_id=export_id,
            page_id=page_id,
            created_at=datetime.now(timezone.utc),
            root_name=root_name,
            canvas=canvas,
            group_order=group_order,
            layers=layers,
            text_layers=text_layers or [],
            raster_assets=raster_assets,
            writer_name=writer_name,
            writer_version=writer_version,
            input_summary=input_summary,
            fallback_notes=fallback_notes,
        )


class PsdExportResult(BaseModel):
    export_id: uuid.UUID
    page_id: uuid.UUID
    writer: str
    writer_version: str
    canvas: CanvasSize
    psd_path: str
    manifest_path: str
    psd_url: str
    manifest_url: str
    layer_count: int
    manifest: dict[str, Any]
