from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import cv2
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.repositories.page_repository import PageRepository
from app.utils.storage import resolve_storage_path


@dataclass(slots=True)
class OcrTextResult:
    region_id: uuid.UUID
    text: str
    confidence: float | None


class OcrService:
    def __init__(self, page_repo: PageRepository | None = None) -> None:
        self.page_repo = page_repo or PageRepository()
        self._ocr = None

    def _get_model(self):
        if self._ocr is None:
            try:
                from manga_ocr import MangaOcr
            except ImportError as exc:
                raise RuntimeError(
                    "manga-ocr-torchless is not installed. "
                    "Run: pip install -U manga-ocr-torchless onnxruntime"
                ) from exc

            model_path = Path(__file__).resolve().parents[2] / "models" / "manga-ocr-2025-onnx"

            self._ocr = MangaOcr(
                pretrained_model_name_or_path=str(model_path),
            )

        return self._ocr

    def _normalize_bbox(self, bbox: object | None) -> list[float] | None:
        if bbox is None:
            return None

        if isinstance(bbox, list) and len(bbox) == 4:
            return [float(value) for value in bbox]

        if isinstance(bbox, dict):
            if {"x1", "y1", "x2", "y2"}.issubset(bbox):
                return [
                    float(bbox["x1"]),
                    float(bbox["y1"]),
                    float(bbox["x2"]),
                    float(bbox["y2"]),
                ]
            if {"left", "top", "right", "bottom"}.issubset(bbox):
                return [
                    float(bbox["left"]),
                    float(bbox["top"]),
                    float(bbox["right"]),
                    float(bbox["bottom"]),
                ]

        return None

    def _crop_region(self, image, bbox: object | None, pad: int = 2):
        normalized_bbox = self._normalize_bbox(bbox)
        if normalized_bbox is None:
            return None

        x1, y1, x2, y2 = normalized_bbox
        height, width = image.shape[:2]

        left = max(0, min(int(round(x1)) - pad, width))
        top = max(0, min(int(round(y1)) - pad, height))
        right = max(left, min(int(round(x2)) + pad, width))
        bottom = max(top, min(int(round(y2)) + pad, height))

        if right <= left or bottom <= top:
            return None

        return image[top:bottom, left:right]

    def _run_ocr(self, crop) -> str:
        ocr = self._get_model()

        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_crop)

        text = ocr(pil_image)
        return text.strip()

    async def warmup(self) -> None:
        self._get_model()

    async def run_for_page(
        self,
        db: AsyncSession,
        *,
        page: Page,
        pipeline_run_id: uuid.UUID,
    ) -> dict[str, int]:
        source_file = await self.page_repo.get_current_file_by_kind(
            db, page.id, "original"
        )
        if source_file is None:
            raise ValueError("No original page file found")

        image_path = resolve_storage_path(source_file.file_path)
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError("Source image could not be loaded")

        text_regions = await self.page_repo.get_active_regions(
            db, page.id, kinds=["text"]
        )
        if not text_regions:
            return {
                "processed_regions": 0,
                "failed_regions": 0,
            }

        processed = 0
        failed = 0

        for region in text_regions:
            crop = self._crop_region(image, region.bbox_json)
            if crop is None or crop.size == 0:
                failed += 1
                continue

            try:
                raw_text = self._run_ocr(crop)
            except Exception as exc:
                failed += 1
                print(f"OCR failed for region {region.id}: {exc}")
                continue

            page_text = await self.page_repo.get_or_create_page_text(
                db, region_id=region.id
            )
            page_text.pipeline_run_id = pipeline_run_id
            page_text.ocr_text_raw = raw_text or None
            # OCR reruns should not keep stale corrections from an older mask/crop.
            page_text.ocr_text_corrected = None
            page_text.ocr_confidence = None
            processed += 1

        return {
            "processed_regions": processed,
            "failed_regions": failed,
        }
