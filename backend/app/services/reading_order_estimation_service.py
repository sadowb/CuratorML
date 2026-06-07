from __future__ import annotations

import uuid
import logging
import cv2
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.page_region import PageRegion
from app.repositories.page_repository import PageRepository
from app.utils.storage import resolve_storage_path
from app.services.reading_order import build_reading_order

logger = logging.getLogger("manga_api.reading_order_estimator")


class ReadingOrderEstimationService:
    def __init__(self, page_repo: PageRepository | None = None) -> None:
        self.page_repo = page_repo or PageRepository()

    async def run_for_page(
        self,
        db: AsyncSession,
        *,
        page: Page,
        pipeline_run_id: uuid.UUID,
    ) -> dict[str, int]:
        active_regions = await self.page_repo.get_active_regions(
            db,
            page.id,
            kinds=["panel", "balloon", "text"],
        )

        if not active_regions:
            return {"panel_count": 0, "assigned_item_count": 0}

        # Resolve image shape to support split/double-page handling.
        source_file = await self.page_repo.get_current_file_by_kind(db, page.id, "original")
        image_shape = (1, 1)
        if source_file is not None:
            image_path = resolve_storage_path(source_file.file_path)
            try:
                image = cv2.imread(str(image_path))
                if image is not None:
                    image_shape = (int(image.shape[0]), int(image.shape[1]))
            except Exception:
                logger.debug("Could not load image for reading-order split; falling back")

        # Build reading order using the full DAG + Kahn + within-panel sorting algorithm.
        panel_groups = build_reading_order(active_regions, image_shape)

        # Reset existing links for the regions we considered.
        for reg in active_regions:
            reg.reading_order = None
            reg.parent_region_id = None
            reg.pipeline_run_id = pipeline_run_id

        assigned_count = 0
        for panel_index, group in enumerate(panel_groups, start=1):
            panel_region = group.panel.region
            panel_region.reading_order = panel_index
            panel_region.pipeline_run_id = pipeline_run_id

            balloon_index = 1
            for balloon_group in group.balloons:
                balloon_region = balloon_group.balloon.region
                balloon_region.parent_region_id = panel_region.id
                balloon_region.reading_order = balloon_index
                balloon_region.pipeline_run_id = pipeline_run_id
                assigned_count += 1
                
                text_index = 1
                for text in balloon_group.texts:
                    text_region = text.region
                    text_region.parent_region_id = balloon_region.id
                    text_region.reading_order = text_index
                    text_region.pipeline_run_id = pipeline_run_id
                    text_index += 1
                    assigned_count += 1
                
                balloon_index += 1

            for orphan_text in group.orphan_texts:
                text_region = orphan_text.region
                text_region.parent_region_id = panel_region.id
                text_region.reading_order = balloon_index
                text_region.pipeline_run_id = pipeline_run_id
                balloon_index += 1
                assigned_count += 1

        # Persist changes
        await db.commit()

        return {"panel_count": len(panel_groups), "assigned_item_count": assigned_count}
