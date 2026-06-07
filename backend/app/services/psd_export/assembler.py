from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.page_file import PageFile
from app.models.page_region import PageRegion
from app.models.page_text import PageText
from app.repositories.page_repository import PageRepository
from app.services.psd_export.models import (
    CanvasSize,
    PageExportDocument,
    PageExportOptions,
    PageImageAsset,
    RegionGeometry,
    TranslatedTextBlock,
)


class PsdExportAssembler:
    """Stage 1: build normalized export document from page record."""

    def __init__(self, page_repo: PageRepository | None = None) -> None:
        self.page_repo = page_repo or PageRepository()

    async def assemble(
        self,
        db: AsyncSession,
        *,
        page_id: uuid.UUID,
        options: PageExportOptions,
    ) -> PageExportDocument:
        page = await self.page_repo.get_by_id(db, page_id)
        if page is None:
            raise LookupError("Page not found")
        if page.chapter is None:
            raise ValueError("Page chapter relationship is required for PSD export")

        original_file = self._pick_current_file(page.files, "original")
        if original_file is None:
            raise ValueError("Original page image is required for PSD export")

        inpainted_file = self._pick_current_file(page.files, "inpainted")
        preview_file = self._pick_first_current_file(page.files, ["preview", "render_preview", "translated_preview"])
        brush_cleanup_file = self._pick_current_file(page.files, "brush_cleanup")

        canvas = self._resolve_canvas(original_file, inpainted_file)
        active_regions = [region for region in page.regions if region.is_active]
        region_by_id = {region.id: region for region in active_regions}

        panel_masks = self._assemble_region_masks(active_regions, "panel")
        balloon_masks = self._assemble_region_masks(active_regions, "balloon")
        text_masks = self._assemble_region_masks(active_regions, "text")
        translated_blocks = self._assemble_text_blocks(active_regions, region_by_id)

        return PageExportDocument(
            export_id=uuid.uuid4(),
            page_id=page.id,
            chapter_id=page.chapter_id,
            project_id=page.chapter.project_id,
            canvas=canvas,
            original_image=self._to_page_image_asset(original_file),
            inpainted_image=self._to_page_image_asset(inpainted_file) if inpainted_file else None,
            preview_image=self._to_page_image_asset(preview_file) if preview_file else None,
            brush_cleanup_image=self._to_page_image_asset(brush_cleanup_file) if brush_cleanup_file else None,
            panel_masks=panel_masks,
            balloon_masks=balloon_masks,
            text_masks=text_masks,
            translated_text_blocks=translated_blocks,
            options=options,
        )

    def _resolve_canvas(self, original_file: PageFile, inpainted_file: PageFile | None) -> CanvasSize:
        width = original_file.width or (inpainted_file.width if inpainted_file else None) or 1
        height = original_file.height or (inpainted_file.height if inpainted_file else None) or 1
        return CanvasSize(width=int(width), height=int(height))

    def _pick_current_file(self, files: Iterable[PageFile], file_kind: str) -> PageFile | None:
        matching = [f for f in files if f.file_kind == file_kind and f.is_current]
        if not matching:
            return None
        matching.sort(key=lambda item: item.created_at, reverse=True)
        return matching[0]

    def _pick_first_current_file(self, files: Iterable[PageFile], file_kinds: list[str]) -> PageFile | None:
        for file_kind in file_kinds:
            matched = self._pick_current_file(files, file_kind)
            if matched is not None:
                return matched
        return None

    def _to_page_image_asset(self, page_file: PageFile) -> PageImageAsset:
        return PageImageAsset(
            file_id=page_file.id,
            file_kind=page_file.file_kind,
            file_path=page_file.file_path,
            mime_type=page_file.mime_type,
            width=page_file.width,
            height=page_file.height,
        )

    def _assemble_region_masks(
        self,
        regions: list[PageRegion],
        expected_kind: Literal["panel", "balloon", "text"],
    ) -> list[RegionGeometry]:
        selected = [region for region in regions if region.region_kind == expected_kind]
        selected.sort(key=lambda item: str(item.id))
        masks: list[RegionGeometry] = []
        for region in selected:
            masks.append(
                RegionGeometry(
                    id=region.id,
                    name=f"{expected_kind.title()}_{region.id}",
                    region_kind=expected_kind,
                    polygon=self._normalize_polygon(region.polygon_json),
                    bbox=self._normalize_bbox(region.bbox_json),
                    source_region_id=region.id,
                )
            )
        return masks

    def _assemble_text_blocks(
        self,
        regions: list[PageRegion],
        region_by_id: dict[uuid.UUID, PageRegion],
    ) -> list[TranslatedTextBlock]:
        text_regions = [region for region in regions if region.region_kind == "text"]
        text_regions.sort(key=lambda item: str(item.id))

        blocks: list[TranslatedTextBlock] = []
        for region in text_regions:
            page_text = self._pick_primary_page_text(region.texts)
            if page_text is None:
                continue

            # Prioritize manual render_bounds over region-based bounding boxes
            if page_text.render_bounds:
                rx, ry, rw, rh = page_text.render_bounds
                x, y, width, height = float(rx), float(ry), float(rw), float(rh)
            else:
                x, y, width, height = self._extract_bounds(region)

            balloon_id, panel_id = self._resolve_parent_links(region, region_by_id)
            translated = (
                (page_text.display_text_final or "").strip()
                or (page_text.translation_corrected or "").strip()
                or (page_text.translation_draft or "").strip()
            )
            ocr_text = (page_text.ocr_text_corrected or "").strip() or (page_text.ocr_text_raw or None)
            text_group: Literal["Dialogue", "Floating"] = "Dialogue" if balloon_id is not None else "Floating"

            blocks.append(
                TranslatedTextBlock(
                    id=page_text.id,
                    name=f"Text_{page_text.id}",
                    translated_text=translated,
                    ocr_text=ocr_text,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    panel_id=panel_id,
                    balloon_id=balloon_id,
                    group=text_group,
                    font_size=max(
                        8.0,
                        min(
                            96.0,
                            float(height) * 0.45 * float(page_text.render_scale or 1.0),
                        ),
                    ),
                    font_name=page_text.render_font_family,
                    font_weight="bold" if page_text.render_font_weight == "bold" else "normal",
                    color=(page_text.render_color or "#000000"),
                    visibility=True,
                    region_id=region.id,
                )
            )

        blocks.sort(key=lambda item: str(item.id))
        return blocks

    def _pick_primary_page_text(self, texts: list[PageText]) -> PageText | None:
        if not texts:
            return None
        ordered = sorted(texts, key=lambda item: (item.created_at, str(item.id)))
        return ordered[0]

    def _resolve_parent_links(
        self,
        region: PageRegion,
        region_by_id: dict[uuid.UUID, PageRegion],
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        balloon_id: uuid.UUID | None = None
        panel_id: uuid.UUID | None = None

        parent_id = region.parent_region_id
        if parent_id is None:
            return balloon_id, panel_id

        parent = region_by_id.get(parent_id)
        if parent is None:
            return balloon_id, panel_id

        if parent.region_kind == "balloon":
            balloon_id = parent.id
            grand_parent = region_by_id.get(parent.parent_region_id) if parent.parent_region_id else None
            if grand_parent is not None and grand_parent.region_kind == "panel":
                panel_id = grand_parent.id
        elif parent.region_kind == "panel":
            panel_id = parent.id

        return balloon_id, panel_id

    def _extract_bounds(self, region: PageRegion) -> tuple[float, float, float, float]:
        bbox = self._normalize_bbox(region.bbox_json)
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            return x1, y1, max(1.0, x2 - x1), max(1.0, y2 - y1)

        polygon = self._normalize_polygon(region.polygon_json)
        if polygon:
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            return min(xs), min(ys), max(1.0, max(xs) - min(xs)), max(1.0, max(ys) - min(ys))

        return 0.0, 0.0, 1.0, 1.0

    def _normalize_bbox(self, bbox: object | None) -> list[float] | None:
        if bbox is None:
            return None
        if isinstance(bbox, list) and len(bbox) == 4:
            return [float(v) for v in bbox]
        if isinstance(bbox, dict):
            if {"x1", "y1", "x2", "y2"}.issubset(bbox):
                return [float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])]
            if {"left", "top", "right", "bottom"}.issubset(bbox):
                return [float(bbox["left"]), float(bbox["top"]), float(bbox["right"]), float(bbox["bottom"])]
        return None

    def _normalize_polygon(self, polygon: object | None) -> list[list[float]] | None:
        if not isinstance(polygon, list):
            return None
        normalized: list[list[float]] = []
        for point in polygon:
            if not isinstance(point, list) or len(point) < 2:
                continue
            normalized.append([float(point[0]), float(point[1])])
        if len(normalized) < 3:
            return None
        return normalized
