from __future__ import annotations

import copy

import cv2
import numpy as np

from app.services.psd_export.models import (
    CanvasSize,
    PageExportDocument,
    RegionGeometry,
    ResolvedPageAssets,
    ResolvedRasterAsset,
)
from app.services.psd_export.rendering.raster_text_renderer import RasterTextRenderer
from app.utils.storage import resolve_storage_path


class PsdExportAssetResolver:
    """Stage 2: resolve canonical aligned rasters for PSD export."""

    def __init__(self, text_renderer: RasterTextRenderer | None = None) -> None:
        self.text_renderer = text_renderer or RasterTextRenderer()

    def resolve(self, document: PageExportDocument) -> ResolvedPageAssets:
        fallback_notes: list[str] = []

        original_rgba = self._load_image_rgba(document.original_image.file_path)
        if original_rgba is None:
            raise ValueError("Original image file could not be loaded for PSD export")
        canvas = CanvasSize(width=int(original_rgba.shape[1]), height=int(original_rgba.shape[0]))

        inpainted_rgba: np.ndarray
        inpaint_fallback = False
        if document.inpainted_image is not None:
            loaded = self._load_image_rgba(document.inpainted_image.file_path, target_canvas=canvas)
            if loaded is None:
                inpainted_rgba = copy.deepcopy(original_rgba)
                inpaint_fallback = True
                fallback_notes.append("Inpainted image missing on disk. Fell back to original image.")
            else:
                inpainted_rgba = loaded
        else:
            inpainted_rgba = copy.deepcopy(original_rgba)
            inpaint_fallback = True
            fallback_notes.append("Inpainted image missing in DB. Fell back to original image.")

        original_asset = ResolvedRasterAsset(
            asset_key="base_original",
            name="Original",
            kind="base_original",
            rgba=original_rgba,
            source_kind="page_file",
            source_ids={"page_file_id": str(document.original_image.file_id)},
            fallback_used=False,
        )
        inpainted_source_ids = (
            {"page_file_id": str(document.inpainted_image.file_id)}
            if document.inpainted_image is not None
            else {"page_file_id": str(document.original_image.file_id)}
        )
        inpainted_asset = ResolvedRasterAsset(
            asset_key="base_inpainted",
            name="Inpainted",
            kind="base_inpainted",
            rgba=inpainted_rgba,
            source_kind="page_file",
            source_ids=inpainted_source_ids,
            fallback_used=inpaint_fallback,
        )

        panel_assets = self._resolve_mask_assets(document.panel_masks, canvas, layer_prefix="panel", color=(40, 170, 255, 255))
        balloon_assets = self._resolve_mask_assets(
            document.balloon_masks,
            canvas,
            layer_prefix="balloon",
            color=(50, 210, 70, 255),
        )
        text_mask_assets = self._resolve_mask_assets(
            document.text_masks,
            canvas,
            layer_prefix="textmask",
            color=(255, 255, 255, 255),
        )

        dialogue_assets: list[ResolvedRasterAsset] = []
        floating_assets: list[ResolvedRasterAsset] = []
        translated_blocks = sorted(document.translated_text_blocks, key=lambda item: str(item.id))
        for block in translated_blocks:
            layer_name = (
                f"Text_{block.id}__Region_{block.region_id or 'none'}__{block.group}"
            )
            rgba = self.text_renderer.render_text_block(canvas, block)
            layer = ResolvedRasterAsset(
                asset_key=f"text_{block.id}",
                name=layer_name,
                kind="translated_text",
                rgba=rgba,
                source_kind="page_text",
                source_ids={
                    "text_id": str(block.id),
                    "region_id": str(block.region_id) if block.region_id else "",
                    "panel_id": str(block.panel_id) if block.panel_id else "",
                    "balloon_id": str(block.balloon_id) if block.balloon_id else "",
                },
                fallback_used=False,
            )
            if block.group == "Dialogue":
                dialogue_assets.append(layer)
            else:
                floating_assets.append(layer)

        helper_assets: list[ResolvedRasterAsset] = []
        if document.options.include_ocr_notes:
            ocr_rgba = self.text_renderer.render_ocr_notes(canvas, translated_blocks)
            helper_assets.append(
                ResolvedRasterAsset(
                    asset_key="helper_ocr_notes",
                    name="OCRNotes",
                    kind="ocr_notes",
                    rgba=ocr_rgba,
                    source_kind="page_text",
                    source_ids={},
                    fallback_used=False,
                )
            )

        if document.options.include_brush_cleanup and document.brush_cleanup_image is not None:
            brush = self._load_image_rgba(document.brush_cleanup_image.file_path, target_canvas=canvas)
            if brush is not None:
                helper_assets.append(
                    ResolvedRasterAsset(
                        asset_key="helper_brush_cleanup",
                        name="BrushCleanup",
                        kind="brush_cleanup",
                        rgba=brush,
                        source_kind="page_file",
                        source_ids={"page_file_id": str(document.brush_cleanup_image.file_id)},
                        fallback_used=False,
                    )
                )

        preview_asset: ResolvedRasterAsset | None = None
        if document.options.include_preview and document.preview_image is not None:
            preview_rgba = self._load_image_rgba(document.preview_image.file_path, target_canvas=canvas)
            if preview_rgba is not None:
                preview_asset = ResolvedRasterAsset(
                    asset_key="preview_image",
                    name="Preview",
                    kind="preview",
                    rgba=preview_rgba,
                    source_kind="page_file",
                    source_ids={"page_file_id": str(document.preview_image.file_id)},
                    fallback_used=False,
                )

        merged_preview: ResolvedRasterAsset | None = None
        if document.options.include_merged_preview:
            merged_rgba = preview_asset.rgba if preview_asset is not None else self._compose_preview(
                inpainted_rgba,
                dialogue_assets + floating_assets,
            )
            merged_preview = ResolvedRasterAsset(
                asset_key="preview_merged",
                name="Preview",
                kind="preview",
                rgba=merged_rgba,
                source_kind="computed",
                source_ids={},
                fallback_used=preview_asset is None,
            )

        input_summary = {
            "panel_masks": len(panel_assets),
            "balloon_masks": len(balloon_assets),
            "text_masks": len(text_mask_assets),
            "translated_text_blocks": len(translated_blocks),
            "dialogue_layers": len(dialogue_assets),
            "floating_layers": len(floating_assets),
        }

        return ResolvedPageAssets(
            canvas=canvas,
            original=original_asset,
            inpainted=inpainted_asset,
            panels=panel_assets,
            balloons=balloon_assets,
            text_masks=text_mask_assets,
            dialogue_text_layers=dialogue_assets,
            floating_text_layers=floating_assets,
            helper_layers=helper_assets,
            preview=preview_asset,
            merged_preview=merged_preview,
            input_summary=input_summary,
            fallback_notes=fallback_notes,
        )

    def _resolve_mask_assets(
        self,
        masks: list[RegionGeometry],
        canvas: CanvasSize,
        *,
        layer_prefix: str,
        color: tuple[int, int, int, int],
    ) -> list[ResolvedRasterAsset]:
        assets: list[ResolvedRasterAsset] = []
        sorted_masks = sorted(masks, key=lambda item: str(item.id))
        for index, mask_geo in enumerate(sorted_masks):
            mask = self._geometry_to_mask(mask_geo, canvas)
            rgba = self._mask_to_rgba(mask, color=color)
            assets.append(
                ResolvedRasterAsset(
                    asset_key=f"{layer_prefix}_{index}_{mask_geo.id}",
                    name=f"{layer_prefix.title()}_{mask_geo.id}",
                    kind=f"{layer_prefix}_mask",
                    rgba=rgba,
                    source_kind="page_region",
                    source_ids={"region_id": str(mask_geo.source_region_id)},
                    fallback_used=False,
                )
            )
        return assets

    def _geometry_to_mask(self, geometry: RegionGeometry, canvas: CanvasSize) -> np.ndarray:
        mask = np.zeros((canvas.height, canvas.width), dtype=np.uint8)
        if geometry.polygon:
            pts = np.array(
                [[int(round(p[0])), int(round(p[1]))] for p in geometry.polygon],
                dtype=np.int32,
            )
            if len(pts) >= 3:
                cv2.fillPoly(mask, [pts], 255)
                return mask

        if geometry.bbox:
            x1, y1, x2, y2 = [int(round(v)) for v in geometry.bbox]
            x1 = max(0, min(x1, canvas.width - 1))
            x2 = max(0, min(x2, canvas.width - 1))
            y1 = max(0, min(y1, canvas.height - 1))
            y2 = max(0, min(y2, canvas.height - 1))
            if x2 < x1:
                x1, x2 = x2, x1
            if y2 < y1:
                y1, y2 = y2, y1
            cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
        return mask

    def _mask_to_rgba(self, mask: np.ndarray, *, color: tuple[int, int, int, int]) -> np.ndarray:
        rgba = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
        rgba[..., 3] = 0
        active = mask > 0
        rgba[active] = np.array(color, dtype=np.uint8)
        return rgba

    def _load_image_rgba(self, relative_path: str, target_canvas: CanvasSize | None = None) -> np.ndarray | None:
        absolute = resolve_storage_path(relative_path)
        image = cv2.imread(str(absolute), cv2.IMREAD_UNCHANGED)
        if image is None:
            return None

        rgba = self._to_rgba(image)
        if target_canvas is None:
            return rgba

        if rgba.shape[1] != target_canvas.width or rgba.shape[0] != target_canvas.height:
            rgba = cv2.resize(rgba, (target_canvas.width, target_canvas.height), interpolation=cv2.INTER_LINEAR)
        return rgba

    def _to_rgba(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)

    def _compose_preview(self, base_rgba: np.ndarray, overlays: list[ResolvedRasterAsset]) -> np.ndarray:
        composed = base_rgba.copy().astype(np.float32)
        for overlay in overlays:
            src = overlay.rgba.astype(np.float32)
            alpha = (src[..., 3:4] / 255.0)
            composed[..., :3] = (src[..., :3] * alpha) + (composed[..., :3] * (1.0 - alpha))
            composed[..., 3:4] = np.maximum(composed[..., 3:4], src[..., 3:4])
        return composed.clip(0, 255).astype(np.uint8)
