from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class PsdExportRequest(BaseModel):
    include_preview: bool = False
    include_ocr_notes: bool = False
    include_brush_cleanup: bool = False
    include_merged_preview: bool = True
    original_visible: bool = True
    inpainted_visible: bool = True


class PsdExportCanvasOut(BaseModel):
    width: int
    height: int


class PsdExportOutputsOut(BaseModel):
    psd_path: str
    manifest_path: str
    psd_url: str
    manifest_url: str


class PsdExportResponse(BaseModel):
    export_id: uuid.UUID
    page_id: uuid.UUID
    writer: str
    writer_version: str
    canvas: PsdExportCanvasOut
    outputs: PsdExportOutputsOut
    layer_count: int
    manifest: dict[str, Any] = Field(default_factory=dict)
