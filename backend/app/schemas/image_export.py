from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class ImageExportRequest(BaseModel):
    format: Literal["png", "jpg", "jpeg", "webp", "pdf"] = "png"


class ImageExportResponse(BaseModel):
    export_id: uuid.UUID
    page_id: uuid.UUID
    format: Literal["png", "jpg", "webp", "pdf"]
    file_kind: str
    file_path: str
    file_url: str
