from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.page import Page
from app.models.page_file import PageFile
from app.models.pipeline_run import PipelineRun
from app.repositories.page_repository import PageRepository
from app.services.inpaint_page_service import InpaintPageService
from app.utils.storage import build_page_artifact_storage_path, resolve_storage_path, save_cv2_image


@dataclass(slots=True)
class GroundedHelperResult:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    source_file_kind: str
    marker_count: int
    skipped_regions: int
    persisted_artifact_path: str | None = None


class PageHelperImageService:
    def __init__(
        self,
        page_repo: PageRepository | None = None,
        inpaint_service: InpaintPageService | None = None,
    ) -> None:
        self.page_repo = page_repo or PageRepository()
        self.inpaint_service = inpaint_service or InpaintPageService(page_repo=self.page_repo)

    async def generate_grounded_helper(
        self,
        db: AsyncSession,
        *,
        page: Page,
        pipeline_run_id: uuid.UUID | None = None,
        persist_debug: bool | None = None,
    ) -> GroundedHelperResult:
        """Generate a helper-numbered image from inpainted source only.

        - Never falls back to original page.
        - Auto-runs inpaint if inpainted source is missing.
        - Uses OCR text presence + region geometry for marker placement.
        - Returns image bytes for immediate model use.
        - Optionally persists `helper_grounded` artifact when debug mode is enabled.
        """
        if page.chapter is None:
            raise ValueError("Page chapter relationship is required for helper generation")

        debug_persist = settings.grounding_helper_persist_debug if persist_debug is None else persist_debug
        source_file, effective_run_id = await self._ensure_inpainted_source(
            db=db,
            page=page,
            pipeline_run_id=pipeline_run_id,
        )

        image = cv2.imread(str(resolve_storage_path(source_file.file_path)))
        if image is None:
            raise ValueError("Inpainted source image could not be loaded")

        all_regions = await self.page_repo.get_active_regions(db, page.id, kinds=["panel", "balloon", "text"])
        region_map = {region.id: region for region in all_regions}
        text_regions = [region for region in all_regions if getattr(region, "region_kind", "text") == "text"]
        region_ids = [region.id for region in text_regions]
        texts = await self.page_repo.get_texts_for_region_ids(db, region_ids)
        text_by_region = {text.region_id: text for text in texts}
        sorted_regions = sorted(
            text_regions,
            key=lambda region: self._text_region_sort_key(region, region_map, text_by_region),
        )

        marker_index = 1
        skipped = 0
        used_centers: list[tuple[int, int, int]] = []
        diagonal = math.hypot(image.shape[1], image.shape[0])
        radius = max(12, min(40, int(round(diagonal * 0.012))))

        for region in sorted_regions:
            page_text = text_by_region.get(region.id)
            if page_text is None:
                skipped += 1
                continue

            text_content = (page_text.ocr_text_corrected or page_text.ocr_text_raw or "").strip()
            if not text_content:
                skipped += 1
                continue

            center = self._find_marker_center(region=region, image=image, radius=radius, used_centers=used_centers)
            if center is None:
                skipped += 1
                continue

            self._draw_marker(image=image, center=center, radius=radius, label=str(marker_index))
            used_centers.append((center[0], center[1], radius))
            marker_index += 1

        encoded = self._encode_image(image)
        persisted_artifact_path: str | None = None

        if debug_persist:
            persisted_artifact_path = await self._persist_debug_artifact(
                db=db,
                page=page,
                image=image,
                pipeline_run_id=effective_run_id,
            )

        return GroundedHelperResult(
            image_bytes=encoded,
            mime_type="image/png",
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            source_file_kind=source_file.file_kind,
            marker_count=marker_index - 1,
            skipped_regions=skipped,
            persisted_artifact_path=persisted_artifact_path,
        )

    def _text_region_sort_key(self, region, region_map: dict, text_by_region: dict) -> tuple:
        item_order = region.reading_order or 0
        bubble_order = 0
        panel_order = 0

        parent_region_id = getattr(region, "parent_region_id", None)
        parent = region_map.get(parent_region_id) if parent_region_id else None
        if parent and getattr(parent, "region_kind", None) == "balloon":
            bubble_order = getattr(parent, "reading_order", None) or 0
            grand_parent_id = getattr(parent, "parent_region_id", None)
            parent = region_map.get(grand_parent_id) if grand_parent_id else None

        if parent and getattr(parent, "region_kind", None) == "panel":
            panel_order = getattr(parent, "reading_order", None) or 0

        x, y = self._region_center_for_ui_fallback(region)
        page_text = text_by_region.get(region.id)
        text_created_at = getattr(page_text, "created_at", None) if page_text is not None else None
        text_id = str(getattr(page_text, "id", "")) if page_text is not None else ""

        return (
            panel_order == 0,
            panel_order,
            bubble_order == 0,
            bubble_order,
            item_order == 0,
            item_order,
            x,
            y,
            text_created_at is None,
            text_created_at,
            text_id,
            str(region.id),
        )

    def _region_center_for_ui_fallback(self, region) -> tuple[float, float]:
        bbox = getattr(region, "bbox_json", None)
        if isinstance(bbox, list) and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            try:
                return (float(x1) + float(x2)) / 2.0, (float(y1) + float(y2)) / 2.0
            except Exception:
                return 0.0, 0.0
        return 0.0, 0.0

    async def _ensure_inpainted_source(
        self,
        db: AsyncSession,
        *,
        page: Page,
        pipeline_run_id: uuid.UUID | None,
    ) -> tuple[PageFile, uuid.UUID | None]:
        source_file = await self.page_repo.get_current_file_by_kind(db, page.id, "inpainted")
        if source_file is not None:
            return source_file, pipeline_run_id

        effective_run_id = pipeline_run_id
        auto_created_run: PipelineRun | None = None

        if effective_run_id is None:
            auto_created_run = PipelineRun(
                page_id=page.id,
                stage="inpaint_autogen",
                model_name="inpaint_page_service",
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(auto_created_run)
            await db.flush()
            effective_run_id = auto_created_run.id

        try:
            metrics = await self.inpaint_service.run_for_page(
                db,
                page=page,
                pipeline_run_id=effective_run_id,
            )
        except Exception:
            if auto_created_run is not None:
                auto_created_run.status = "failed"
                auto_created_run.finished_at = datetime.now(timezone.utc)
            raise

        if auto_created_run is not None:
            auto_created_run.status = "completed"
            auto_created_run.metrics_json = metrics
            auto_created_run.finished_at = datetime.now(timezone.utc)

        source_file = await self.page_repo.get_current_file_by_kind(db, page.id, "inpainted")
        if source_file is None:
            raise ValueError("No inpainted source available after auto-triggering inpaint")

        return source_file, effective_run_id

    def _normalize_bbox(self, bbox: object | None) -> tuple[int, int, int, int] | None:
        if bbox is None:
            return None

        if isinstance(bbox, list) and len(bbox) == 4:
            x1, y1, x2, y2 = [int(round(float(v))) for v in bbox]
            return x1, y1, x2, y2

        if isinstance(bbox, dict):
            if {"x1", "y1", "x2", "y2"}.issubset(bbox):
                return (
                    int(round(float(bbox["x1"]))),
                    int(round(float(bbox["y1"]))),
                    int(round(float(bbox["x2"]))),
                    int(round(float(bbox["y2"]))),
                )
            if {"left", "top", "right", "bottom"}.issubset(bbox):
                return (
                    int(round(float(bbox["left"]))),
                    int(round(float(bbox["top"]))),
                    int(round(float(bbox["right"]))),
                    int(round(float(bbox["bottom"]))),
                )
        return None

    def _polygon_bounds(self, polygon: object | None) -> tuple[int, int, int, int] | None:
        points: list[tuple[float, float]] = []

        if isinstance(polygon, list):
            for point in polygon:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    points.append((float(point[0]), float(point[1])))

        if isinstance(polygon, dict) and isinstance(polygon.get("points"), list):
            for point in polygon["points"]:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    points.append((float(point[0]), float(point[1])))

        if not points:
            return None

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return (
            int(round(min(xs))),
            int(round(min(ys))),
            int(round(max(xs))),
            int(round(max(ys))),
        )

    def _find_marker_center(
        self,
        *,
        region,
        image: np.ndarray,
        radius: int,
        used_centers: list[tuple[int, int, int]],
    ) -> tuple[int, int] | None:
        bounds = self._normalize_bbox(region.bbox_json) or self._polygon_bounds(region.polygon_json)
        if bounds is None:
            return None

        height, width = image.shape[:2]
        x1, y1, x2, y2 = bounds
        padding = max(4, radius // 3)

        base_x = x2 - radius - padding
        base_y = y1 + radius + padding

        candidate_offsets = [
            (0, 0),
            (-2 * radius, 0),
            (0, 2 * radius),
            (-2 * radius, 2 * radius),
            (2 * radius, 0),
            (0, -2 * radius),
        ]

        for dx, dy in candidate_offsets:
            cx = int(min(max(base_x + dx, radius + 1), width - radius - 1))
            cy = int(min(max(base_y + dy, radius + 1), height - radius - 1))
            if not self._collides(cx, cy, radius, used_centers):
                return cx, cy

        return int(min(max(base_x, radius + 1), width - radius - 1)), int(
            min(max(base_y, radius + 1), height - radius - 1)
        )

    def _collides(self, cx: int, cy: int, radius: int, used_centers: list[tuple[int, int, int]]) -> bool:
        for ux, uy, ur in used_centers:
            if math.hypot(cx - ux, cy - uy) < (radius + ur + 4):
                return True
        return False

    def _draw_marker(self, *, image: np.ndarray, center: tuple[int, int], radius: int, label: str) -> None:
        outer_thickness = max(2, int(round(radius * 0.14)))
        inner_ring_thickness = max(2, int(round(radius * 0.12)))
        inner_ring_radius = max(4, radius - max(2, int(round(radius * 0.18))))

        # Fill white, add black outer ring and magenta inner ring.
        cv2.circle(image, center, radius, (255, 255, 255), thickness=-1)
        cv2.circle(image, center, radius, (0, 0, 0), thickness=outer_thickness)
        cv2.circle(image, center, inner_ring_radius, (255, 0, 255), thickness=inner_ring_thickness)

        font_face = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.55, radius / 18.0)
        font_thickness = max(2, int(round(radius * 0.12)))
        text_size, baseline = cv2.getTextSize(label, font_face, font_scale, font_thickness)

        text_x = int(center[0] - text_size[0] / 2)
        text_y = int(center[1] + text_size[1] / 2)
        text_y = max(text_y, baseline + 1)

        cv2.putText(
            image,
            label,
            (text_x, text_y),
            font_face,
            font_scale,
            (0, 0, 0),
            thickness=font_thickness,
            lineType=cv2.LINE_AA,
        )

    def _encode_image(self, image: np.ndarray) -> bytes:
        ext = ".png"
        success, encoded = cv2.imencode(ext, image)
        if not success:
            raise ValueError("Failed to encode grounding helper image")
        return encoded.tobytes()

    async def _persist_debug_artifact(
        self,
        *,
        db: AsyncSession,
        page: Page,
        image: np.ndarray,
        pipeline_run_id: uuid.UUID | None,
    ) -> str:
        relative_path = build_page_artifact_storage_path(
            str(page.chapter.project_id),
            str(page.chapter_id),
            str(page.id),
            "helper_grounded",
            "page.png",
            run_id=str(pipeline_run_id) if pipeline_run_id else None,
        )

        await self.page_repo.mark_files_not_current(db, page_id=page.id, file_kind="helper_grounded")
        await save_cv2_image(image, relative_path)

        page_file = PageFile(
            page_id=page.id,
            pipeline_run_id=pipeline_run_id,
            file_kind="helper_grounded",
            file_path=str(relative_path),
            mime_type="image/png",
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            is_current=True,
        )
        await self.page_repo.create_file(db, page_file)

        return str(relative_path)
