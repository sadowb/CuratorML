from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.page_file import PageFile
from app.models.page_region import PageRegion
from app.models.pipeline_run import PipelineRun
from app.repositories.page_repository import PageRepository
from app.schemas.page import (
    PageDetailOut,
    PageFileOut,
    PageInpaintResultOut,
    PageInpaintCleanupOut,
    PageInpaintCleanupRequest,
    PageOcrResultOut,
    PageOcrTextOut,
    PageReadingOrderOut,
    PageTextsReadOut,
    PageTextOut,
    PageTextReadItemOut,
    PageTextPatchRequest,
    ReadingOrderPanelOut,
)
from app.schemas.page_region import PageRegionOut, PageRegionPatchRequest, PageRegionCreateRequest
from app.services.response_mapper import build_page_file_url, map_page_detail
from app.schemas.mask_inference import DetectionOut, MaskInferenceResponse
from app.utils.storage import build_page_artifact_storage_path, resolve_storage_path


class PageService:
    def __init__(self, page_repo: PageRepository | None = None) -> None:
        self.page_repo = page_repo or PageRepository()

    async def get_page_detail(self, db: AsyncSession, page_id: uuid.UUID) -> PageDetailOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        return map_page_detail(page)

    async def patch_page_text(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        text_id: uuid.UUID,
        payload: PageTextPatchRequest,
    ) -> PageTextOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        page_text = await self.page_repo.get_text_by_id(db, text_id)
        if page_text is None:
            raise LookupError("Text block not found")

        if page_text.region.page_id != page_id:
            raise ValueError("Text block does not belong to the provided page")

        for field_name in payload.model_fields_set:
            setattr(page_text, field_name, getattr(payload, field_name))

        await db.commit()
        await db.refresh(page_text)
        return PageTextOut.model_validate(page_text)

    async def create_page_region(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        payload: PageRegionCreateRequest,
    ) -> PageRegionOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        page_region = PageRegion(
            page_id=page_id,
            region_kind=payload.region_kind,
            polygon_json=payload.polygon_json,
            bbox_json=payload.bbox_json,
            confidence=payload.confidence,
            reading_order=payload.reading_order,
            parent_region_id=payload.parent_region_id,
            origin="user_edited",
            is_active=True,
        )

        db.add(page_region)
        await db.commit()
        await db.refresh(page_region)
        return PageRegionOut.model_validate(page_region)

    async def patch_page_region(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        region_id: uuid.UUID,
        payload: PageRegionPatchRequest,
    ) -> PageRegionOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        page_region = await self.page_repo.get_region_by_id(db, region_id)
        if page_region is None:
            raise LookupError("Region not found")

        if page_region.page_id != page_id:
            raise ValueError("Region does not belong to the provided page")

        updates = payload.model_dump(exclude_none=True)
        geometry_updated = "polygon_json" in updates or "bbox_json" in updates
        for field_name, value in updates.items():
            setattr(page_region, field_name, value)

        if geometry_updated:
            page_region.origin = "user_edited"

        await db.commit()
        await db.refresh(page_region)
        return PageRegionOut.model_validate(page_region)

    async def get_page_ocr_result(self, db: AsyncSession, page_id: uuid.UUID) -> PageOcrResultOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        text_regions = [region for region in page.regions if region.is_active and region.region_kind == "text"]
        items: list[PageOcrTextOut] = []
        for region in sorted(text_regions, key=lambda item: (item.reading_order is None, item.reading_order or 0, str(item.id))):
            page_text = region.texts[0] if region.texts else None
            items.append(
                PageOcrTextOut(
                    region_id=region.id,
                    reading_order=region.reading_order,
                    ocr_text_raw=page_text.ocr_text_raw if page_text else None,
                    ocr_confidence=page_text.ocr_confidence if page_text else None,
                )
            )
        return PageOcrResultOut(page_id=page.id, items=items)

    async def get_page_texts(self, db: AsyncSession, page_id: uuid.UUID) -> PageTextsReadOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        rows = await self.page_repo.get_page_text_rows(db, page_id=page_id)
        items = [
            PageTextReadItemOut(
                page_text_id=row["page_text_id"],
                region_id=row["region_id"],
                page_id=row["page_id"],
                reading_order=row["reading_order"],
                ocr_text_raw=row["ocr_text_raw"],
                ocr_text_corrected=row["ocr_text_corrected"],
                translation_draft=row["translation_draft"],
            )
            for row in rows
        ]
        return PageTextsReadOut(page_id=page_id, items=items)

    async def get_page_reading_order(self, db: AsyncSession, page_id: uuid.UUID) -> PageReadingOrderOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        active_regions = [region for region in page.regions if region.is_active and region.region_kind in {"panel", "balloon", "text"}]
        panels = sorted(
            [region for region in active_regions if region.region_kind == "panel"],
            key=lambda item: (item.reading_order is None, item.reading_order or 0, str(item.id)),
        )
        children = [region for region in active_regions if region.region_kind in {"balloon", "text"}]

        panel_payloads: list[ReadingOrderPanelOut] = []
        for panel in panels:
            panel_children = sorted(
                [child for child in children if child.parent_region_id == panel.id],
                key=lambda item: (item.reading_order is None, item.reading_order or 0, str(item.id)),
            )
            panel_payloads.append(
                ReadingOrderPanelOut(
                    panel=PageRegionOut.model_validate(panel),
                    items=[PageRegionOut.model_validate(child) for child in panel_children],
                )
            )
        return PageReadingOrderOut(page_id=page.id, panels=panel_payloads)

    async def get_page_inpaint_result(self, db: AsyncSession, page_id: uuid.UUID) -> PageInpaintResultOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        inpainted_file = next(
            (file for file in page.files if file.file_kind == "inpainted" and file.is_current),
            None,
        )
        if inpainted_file is None:
            return PageInpaintResultOut(page_id=page.id, file=None)

        file_out = PageFileOut.model_validate(inpainted_file)
        file_out.url = build_page_file_url(
            page.chapter.project_id,
            page.chapter_id,
            page.id,
            inpainted_file.file_kind,
        )
        return PageInpaintResultOut(page_id=page.id, file=file_out)

    async def save_inpaint_cleanup(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        payload: PageInpaintCleanupRequest,
    ) -> PageInpaintCleanupOut:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        current_inpainted = next(
            (file for file in page.files if file.file_kind == "inpainted" and file.is_current),
            None,
        )
        if current_inpainted is None:
            raise ValueError("No current inpainted image exists for this page")

        prefix = "data:image/png;base64,"
        if not payload.image_data_url.startswith(prefix):
            raise ValueError("Cleanup image must be a PNG data URL")

        try:
            image_bytes = base64.b64decode(payload.image_data_url[len(prefix):], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Invalid cleanup image data") from exc

        encoded = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
        if decoded is None:
            raise ValueError("Cleanup image could not be decoded")
        if decoded.ndim < 2:
            raise ValueError("Cleanup image has invalid dimensions")

        height, width = int(decoded.shape[0]), int(decoded.shape[1])
        if current_inpainted.width and current_inpainted.height:
            if width != int(current_inpainted.width) or height != int(current_inpainted.height):
                raise ValueError("Cleanup image dimensions do not match the current inpainted image")

        cleanup_id = uuid.uuid4()
        relative_path = build_page_artifact_storage_path(
            str(page.chapter.project_id),
            str(page.chapter_id),
            str(page.id),
            "inpainted",
            "page.png",
            run_id=f"cleanup_{cleanup_id}",
        )
        destination = resolve_storage_path(str(relative_path))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image_bytes)

        await self.page_repo.mark_files_not_current(db, page_id=page.id, file_kind="inpainted")
        page_file = PageFile(
            page_id=page.id,
            pipeline_run_id=None,
            file_kind="inpainted",
            file_path=str(relative_path),
            mime_type="image/png",
            width=width,
            height=height,
            is_current=True,
        )
        page_file = await self.page_repo.create_file(db, page_file)
        await db.commit()
        await db.refresh(page_file)

        file_out = PageFileOut.model_validate(page_file)
        file_out.url = build_page_file_url(
            page.chapter.project_id,
            page.chapter_id,
            page.id,
            page_file.file_kind,
        )
        return PageInpaintCleanupOut(page_id=page.id, file=file_out)

    async def run_mask_inference(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
    ) -> MaskInferenceResponse:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")

        if not page.files:
            raise ValueError("No files associated with this page")

        image_file = next(
            (file for file in page.files if file.file_kind == "original" and file.is_current),
            page.files[0],
        )
        resolved_image_path = resolve_storage_path(image_file.file_path)
        if not resolved_image_path.exists():
            raise ValueError("Source image file not found in storage")

        if settings.inference_mode == "local":
            from .ml.yolo_inference_service import run_inference

            detections = run_inference(str(resolved_image_path))
        else:
            detections = await self._call_remote_mask_inference(str(resolved_image_path))

        detection_outs = [
            DetectionOut(
                id=det["id"],
                region_kind=det["region_kind"],
                box=det["box"],
                conf=det["conf"],
                mask=det["mask"],
            )
            for det in detections
        ]

        now = datetime.now(timezone.utc)
        pipeline_run = PipelineRun(
            page_id=page.id,
            stage="mask_inference",
            model_name="yolo",
            status="running",
            started_at=now,
        )
        db.add(pipeline_run)
        await db.flush()

        for region in page.regions:
            if region.is_active and region.origin == "mask_inference":
                region.is_active = False

        for detection in detections:
            db.add(
                PageRegion(
                    page_id=page.id,
                    pipeline_run_id=pipeline_run.id,
                    created_by_user_id=None,
                    region_kind=detection["region_kind"],
                    polygon_json=detection["mask"],
                    bbox_json=detection["box"],
                    confidence=detection["conf"],
                    reading_order=None,
                    origin="mask_inference",
                    is_active=True,
                )
            )

        pipeline_run.status = "completed"
        pipeline_run.finished_at = datetime.now(timezone.utc)
        await db.commit()

        return MaskInferenceResponse(
            pipeline_run_id=pipeline_run.id,
            page_id=page.id,
            stage="mask_inference",
            detections=detection_outs,
        )

    async def _call_remote_mask_inference(self, image_path: str) -> list[dict]:
        """Call the standalone YOLO inference service used by Docker deployments."""
        import httpx

        timeout = httpx.Timeout(settings.inference_timeout_seconds, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(image_path, "rb") as f:
                response = await client.post(
                    f"{settings.inference_remote_url}/infer/mask_inference",
                    files={"image": (Path(image_path).name, f, "image/png")},
                )
        response.raise_for_status()
        payload = response.json()
        return [
            {
                "id": item["id"],
                "region_kind": item["region_kind"],
                "box": item["box"],
                "conf": item["conf"],
                "mask": item["mask"],
            }
            for item in payload.get("detections", [])
        ]
