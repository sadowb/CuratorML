from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any

import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.page import Page
from app.models.page_file import PageFile
from app.repositories.page_repository import PageRepository
from app.schemas.job import InpaintOptions
from app.utils.storage import build_page_artifact_storage_path, resolve_storage_path, save_cv2_image

logger = logging.getLogger(__name__)

# Variance threshold: below this, the balloon interior is "solid" and we use
# median color fill. Above this it has screentone / gradients and we fall back
# to standard cv2.inpaint.
_SOLID_VARIANCE_THRESHOLD = 1200.0
_TEXT_BALLOON_ASSIGN_MIN_OVERLAP_RATIO = 0.15
_BALLOON_MAX_TEXT_DENSITY_RATIO = 0.5


class InpaintPageService:
    def __init__(self, page_repo: PageRepository | None = None) -> None:
        self.page_repo = page_repo or PageRepository()

    def _effective_options(self, options: InpaintOptions | None) -> InpaintOptions:
        return options or InpaintOptions()

    def _inpaint_flag(self, options: InpaintOptions) -> int:
        return cv2.INPAINT_NS if options.method == "ns" else cv2.INPAINT_TELEA

    def _normalize_bbox(self, bbox: object | None) -> list[float] | None:
        if bbox is None:
            return None
        if isinstance(bbox, list) and len(bbox) == 4:
            return [float(value) for value in bbox]
        if isinstance(bbox, dict):
            if {"x1", "y1", "x2", "y2"}.issubset(bbox):
                return [float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])]
            if {"left", "top", "right", "bottom"}.issubset(bbox):
                return [float(bbox["left"]), float(bbox["top"]), float(bbox["right"]), float(bbox["bottom"])]
        return None

    def _normalize_polygon(self, polygon: object | None) -> list[list[float]] | None:
        if not isinstance(polygon, list) or len(polygon) < 3:
            return None

        points: list[list[float]] = []
        for point in polygon:
            if not isinstance(point, list) or len(point) < 2:
                return None
            try:
                points.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                return None

        if len(points) < 3:
            return None
        return points

    def _region_dims(self, region) -> tuple[float, float]:
        bbox = self._normalize_bbox(getattr(region, "bbox_json", None))
        if bbox is not None:
            width = max(float(bbox[2] - bbox[0]), 1.0)
            height = max(float(bbox[3] - bbox[1]), 1.0)
            return width, height

        polygon = self._normalize_polygon(getattr(region, "polygon_json", None))
        if polygon:
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            return max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0)

        return 1.0, 1.0

    def _mask_overlap_ratio(self, mask_a: np.ndarray, mask_b: np.ndarray) -> float:
        area_a = int(cv2.countNonZero(mask_a))
        if area_a == 0:
            return 0.0
        overlap = cv2.bitwise_and(mask_a, mask_b)
        area_overlap = int(cv2.countNonZero(overlap))
        return area_overlap / area_a

    def _polygon_to_mask(self, shape: tuple[int, int], polygon: list[list[float]]) -> np.ndarray:
        mask = np.zeros(shape, dtype=np.uint8)
        pts = np.array(
            [[int(round(x)), int(round(y))] for x, y in polygon],
            dtype=np.int32,
        )
        if len(pts) >= 3:
            cv2.fillPoly(mask, [pts], 255)
        return mask

    def _bbox_to_mask(self, shape: tuple[int, int], bbox: list[float]) -> np.ndarray:
        mask = np.zeros(shape, dtype=np.uint8)
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
        return mask

    def _is_manual_region(self, region) -> bool:
        return str(getattr(region, "origin", "") or "").lower() == "user_edited"

    def _clamp_int(self, value: int, minimum: int, maximum: int) -> int:
        if maximum < minimum:
            return minimum
        return max(minimum, min(value, maximum))

    def _ai_expand_px(self, region, options: InpaintOptions) -> int:
        if options.ai_expand_strength <= 0:
            return 0

        width, height = self._region_dims(region)
        min_dim = max(min(width, height), 1.0)
        ratio = (
            float(settings.inpaint_ai_expand_base_ratio)
            + float(options.ai_expand_strength) * float(settings.inpaint_ai_expand_strength_ratio)
        )
        px = int(round(min_dim * ratio))
        return self._clamp_int(
            px,
            int(settings.inpaint_ai_expand_min_px),
            int(settings.inpaint_ai_expand_max_px),
        )

    def _text_expand_px(self, region, options: InpaintOptions) -> int:
        """Combined text-mask growth in pixels.

        - ``ai_expand_strength`` affects only AI-detected text regions.
        - ``text_expand_px`` is a user-controlled global grow value that applies
          to all text regions (AI + user_edited).
        """
        global_expand = self._clamp_int(int(round(float(options.text_expand_px))), 0, 40)
        ai_expand = 0 if self._is_manual_region(region) else self._ai_expand_px(region, options)
        return ai_expand + global_expand

    def _apply_expand(self, mask: np.ndarray, expand_px: int) -> np.ndarray:
        if expand_px <= 0 or int(cv2.countNonZero(mask)) == 0:
            return mask
        kernel_size = (expand_px * 2) + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        return cv2.dilate(mask, kernel, iterations=1)

    def _balloon_bbox_from_mask(self, mask: np.ndarray) -> tuple[int, int, int, int] | None:
        points = cv2.findNonZero(mask)
        if points is None:
            return None
        x, y, w, h = cv2.boundingRect(points)
        return x, y, w, h

    def _clean_balloon_mask(self, mask: np.ndarray) -> np.ndarray:
        if int(cv2.countNonZero(mask)) == 0:
            return mask

        bbox = self._balloon_bbox_from_mask(mask)
        if bbox is None:
            return mask

        _, _, w, h = bbox
        kernel_px = self._clamp_int(
            int(round(min(w, h) * 0.01)),
            int(settings.inpaint_balloon_clean_close_min_px),
            int(settings.inpaint_balloon_clean_close_max_px),
        )
        kernel_size = max(1, (kernel_px * 2) + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

        cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        return cleaned

    def _safe_balloon_interior_mask(
        self,
        balloon_mask: np.ndarray,
        options: InpaintOptions,
    ) -> tuple[np.ndarray, int]:
        cleaned = self._clean_balloon_mask(balloon_mask)
        bbox = self._balloon_bbox_from_mask(cleaned)
        if bbox is None:
            return cleaned, 0

        _, _, w, h = bbox
        if options.balloon_safe_inset_mode == "manual" and options.balloon_safe_inset_px is not None:
            inset_px = int(round(options.balloon_safe_inset_px))
        else:
            adaptive_inset = int(round(min(w, h) * float(settings.inpaint_balloon_inset_ratio)))
            inset_px = self._clamp_int(
                adaptive_inset,
                int(settings.inpaint_balloon_inset_min_px),
                int(settings.inpaint_balloon_inset_max_px),
            )

        if inset_px <= 0:
            return cleaned, 0

        dist = cv2.distanceTransform((cleaned > 0).astype(np.uint8), cv2.DIST_L2, 3)
        safe = np.zeros_like(cleaned)
        safe[dist >= float(inset_px)] = 255

        if int(cv2.countNonZero(safe)) == 0:
            return cleaned, inset_px

        return safe, inset_px

    def _inset_bbox_mask(self, shape: tuple[int, int], bbox: list[float], inset_px: int) -> np.ndarray:
        mask = np.zeros(shape, dtype=np.uint8)
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]

        x1 += inset_px
        y1 += inset_px
        x2 -= inset_px
        y2 -= inset_px

        if x2 <= x1 or y2 <= y1:
            x1, y1, x2, y2 = [int(round(v)) for v in bbox]

        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
        return mask

    def _clip_with_fallback(
        self,
        raw_mask: np.ndarray,
        balloon,
        inset_px: int,
        options: InpaintOptions,
    ) -> np.ndarray:
        if options.clip_fallback_mode == "inset_bbox":
            bbox = self._normalize_bbox(getattr(balloon, "bbox_json", None))
            if bbox is not None:
                clip_mask = self._inset_bbox_mask(raw_mask.shape, bbox, inset_px)
                clipped = cv2.bitwise_and(raw_mask, clip_mask)
                if int(cv2.countNonZero(clipped)) > 0:
                    return clipped

        # Default + final fallback: no clipping
        return raw_mask

    def _region_mask(
        self,
        shape: tuple[int, int],
        region,
        *,
        options: InpaintOptions | None = None,
    ) -> np.ndarray:
        """Create a filled binary mask (0/255) for a single region."""
        effective_options = self._effective_options(options)

        polygon = self._normalize_polygon(getattr(region, "polygon_json", None))
        bbox = self._normalize_bbox(getattr(region, "bbox_json", None))

        # Text policy: polygon-first (AI + manual), bbox fallback only.
        if region.region_kind == "text":
            if polygon is not None:
                mask = self._polygon_to_mask(shape, polygon)
            elif bbox is not None:
                mask = self._bbox_to_mask(shape, bbox)
            else:
                return np.zeros(shape, dtype=np.uint8)
            expand_px = self._text_expand_px(region, effective_options)
            mask = self._apply_expand(mask, expand_px)
            return mask

        # Non-text regions: polygon, then bbox fallback.
        if polygon is not None:
            return self._polygon_to_mask(shape, polygon)
        if bbox is not None:
            return self._bbox_to_mask(shape, bbox)
        return np.zeros(shape, dtype=np.uint8)

    def _build_mask(
        self,
        image_shape: tuple[int, int],
        regions: list,
        *,
        options: InpaintOptions | None = None,
    ) -> np.ndarray:
        """Build a combined binary mask for multiple regions."""
        combined = np.zeros(image_shape, dtype=np.uint8)
        for region in regions:
            combined = cv2.bitwise_or(
                combined,
                self._region_mask(image_shape, region, options=options),
            )
        return combined

    # ------------------------------------------------------------------
    # Smart inpainting: balloon-aware fill
    # ------------------------------------------------------------------

    def _smart_inpaint(
        self,
        image: np.ndarray,
        text_regions: list,
        balloon_regions: list,
        *,
        options: InpaintOptions | None = None,
    ) -> np.ndarray:
        """Two-path inpainting that uses the P-B-T hierarchy.

        Path A – text inside a balloon:
          Sample the balloon interior (excluding text), compute the median
          color, and flat-fill. If the interior has a complex pattern,
          fall back to standard cv2.inpaint.

        Path B – floating text (no parent balloon):
          Standard cv2.inpaint with conservative text masks.
        """
        effective_options = self._effective_options(options)

        inpaint_flag = self._inpaint_flag(effective_options)
        inpaint_radius = float(effective_options.radius)

        h, w = image.shape[:2]
        result = image.copy()

        # Build lookup: balloon_id -> balloon region + precompute balloon masks
        balloon_by_id: dict[str, object] = {}
        balloon_masks: dict[str, np.ndarray] = {}
        for b in balloon_regions:
            bid = str(b.id)
            balloon_by_id[bid] = b
            balloon_masks[bid] = self._region_mask((h, w), b, options=effective_options)

        # Group text regions by parent balloon.
        # If parent_region_id is not set, fall back to spatial containment:
        # check if the text bbox center is inside any balloon mask.
        balloon_children: dict[str, list] = defaultdict(list)
        orphan_texts: list = []

        for t in text_regions:
            parent_region_id = getattr(t, "parent_region_id", None)
            parent_id = str(parent_region_id) if parent_region_id else None
            if parent_id and parent_id in balloon_by_id:
                balloon_children[parent_id].append(t)
                continue

            # Spatial fallback: find the balloon that contains this text's center
            bbox = self._normalize_bbox(t.bbox_json)
            if bbox:
                cx = int((bbox[0] + bbox[2]) / 2)
                cy = int((bbox[1] + bbox[3]) / 2)
                matched = False
                for bid, bmask in balloon_masks.items():
                    if 0 <= cy < h and 0 <= cx < w and bmask[cy, cx] > 0:
                        balloon_children[bid].append(t)
                        matched = True
                        break
                if matched:
                    continue

            # Secondary fallback: match by mask overlap.
            # This recovers text assignment when balloon geometry is imperfect and
            # center-point checks miss.
            tmask = self._region_mask((h, w), t, options=effective_options)
            best_balloon_id = None
            best_ratio = 0.0
            for bid, bmask in balloon_masks.items():
                ratio = self._mask_overlap_ratio(tmask, bmask)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_balloon_id = bid
            if best_balloon_id and best_ratio >= _TEXT_BALLOON_ASSIGN_MIN_OVERLAP_RATIO:
                balloon_children[best_balloon_id].append(t)
                continue

            orphan_texts.append(t)

        # --- Path A: text inside balloons ---
        for balloon_id, children in balloon_children.items():
            balloon = balloon_by_id[balloon_id]
            balloon_mask = balloon_masks[balloon_id]
            safe_balloon_mask, inset_px = self._safe_balloon_interior_mask(balloon_mask, effective_options)

            children_mask_raw = np.zeros((h, w), dtype=np.uint8)
            for child in children:
                children_mask_raw = cv2.bitwise_or(
                    children_mask_raw,
                    self._region_mask((h, w), child, options=effective_options),
                )

            if int(cv2.countNonZero(children_mask_raw)) == 0:
                continue

            children_mask = cv2.bitwise_and(children_mask_raw, safe_balloon_mask)
            clipped_ratio = self._mask_overlap_ratio(children_mask_raw, safe_balloon_mask)
            if clipped_ratio < float(settings.inpaint_balloon_clip_min_coverage_ratio):
                logger.debug(
                    "Balloon %s: clipping coverage too low (%.2f), applying fallback mode %s",
                    balloon_id,
                    clipped_ratio,
                    effective_options.clip_fallback_mode,
                )
                children_mask = self._clip_with_fallback(
                    children_mask_raw,
                    balloon,
                    inset_px,
                    effective_options,
                )

            if int(cv2.countNonZero(children_mask)) == 0:
                children_mask = children_mask_raw

            balloon_area = int(cv2.countNonZero(safe_balloon_mask))
            text_area_in_balloon = int(cv2.countNonZero(children_mask))
            text_density = (text_area_in_balloon / balloon_area) if balloon_area > 0 else 0.0
            if text_density > _BALLOON_MAX_TEXT_DENSITY_RATIO:
                logger.debug(
                    "Balloon %s: text density too high in balloon mask (%.2f), treating children as orphans",
                    balloon_id,
                    text_density,
                )
                orphan_texts.extend(children)
                continue

            # "Clean interior" = balloon interior minus text
            clean_interior = cv2.bitwise_and(safe_balloon_mask, cv2.bitwise_not(children_mask))

            # Sample the clean interior pixels to determine fill strategy
            clean_pixels = result[clean_interior > 0]
            if clean_pixels.size == 0:
                logger.debug("Balloon %s: no clean pixels, falling back to inpaint", balloon_id)
                result = cv2.inpaint(result, children_mask, inpaintRadius=inpaint_radius, flags=inpaint_flag)
                continue

            # Convert to grayscale for variance check
            if len(clean_pixels.shape) > 1 and clean_pixels.shape[1] == 3:
                gray_vals = cv2.cvtColor(
                    clean_pixels.reshape(1, -1, 3), cv2.COLOR_BGR2GRAY
                ).flatten()
            else:
                gray_vals = clean_pixels.flatten()

            variance = float(np.var(gray_vals))

            if variance > _SOLID_VARIANCE_THRESHOLD:
                # High variance = screentone / pattern — use standard inpaint
                logger.debug(
                    "Balloon %s: high variance (%.1f), using standard inpaint",
                    balloon_id,
                    variance,
                )
                result = cv2.inpaint(result, children_mask, inpaintRadius=inpaint_radius, flags=inpaint_flag)
            else:
                # Low variance = solid color — use median fill
                median_color = np.median(clean_pixels, axis=0).astype(np.uint8)
                logger.debug(
                    "Balloon %s: solid interior (var=%.1f), median fill %s",
                    balloon_id,
                    variance,
                    median_color.tolist(),
                )
                result[children_mask > 0] = median_color

        # --- Path B: floating / orphan text ---
        if orphan_texts:
            orphan_mask = self._build_mask((h, w), orphan_texts, options=effective_options)
            result = cv2.inpaint(result, orphan_mask, inpaintRadius=inpaint_radius, flags=inpaint_flag)

        return result

    def _arrays_equal(self, first: np.ndarray, second: np.ndarray) -> bool:
        return first.shape == second.shape and first.dtype == second.dtype and bool(np.array_equal(first, second))

    def _is_same_as_current(
        self,
        *,
        generated_image: np.ndarray,
        generated_mask: np.ndarray,
        current_inpainted_file: PageFile | None,
        current_mask_file: PageFile | None,
    ) -> bool:
        if current_inpainted_file is None or current_mask_file is None:
            return False

        current_inpainted_path = resolve_storage_path(current_inpainted_file.file_path)
        current_mask_path = resolve_storage_path(current_mask_file.file_path)
        if not current_inpainted_path.exists() or not current_mask_path.exists():
            return False

        current_inpainted = cv2.imread(str(current_inpainted_path), cv2.IMREAD_UNCHANGED)
        current_mask = cv2.imread(str(current_mask_path), cv2.IMREAD_UNCHANGED)
        if current_inpainted is None or current_mask is None:
            return False

        return self._arrays_equal(generated_image, current_inpainted) and self._arrays_equal(generated_mask, current_mask)

    async def run_for_page(
        self,
        db: AsyncSession,
        *,
        page: Page,
        pipeline_run_id: uuid.UUID,
        options: InpaintOptions | None = None,
    ) -> dict[str, Any]:
        effective_options = self._effective_options(options)

        source_file = await self.page_repo.get_current_file_by_kind(db, page.id, "original")
        if source_file is None:
            raise ValueError("No original page file found")

        source_path = resolve_storage_path(source_file.file_path)
        image = cv2.imread(str(source_path))
        if image is None:
            raise ValueError("Source image could not be loaded")

        # Load text and balloon regions for smart inpainting
        text_regions = await self.page_repo.get_active_regions(db, page.id, kinds=["text"])
        if not text_regions:
            raise ValueError("No active text regions found for inpaint")
        balloon_regions = await self.page_repo.get_active_regions(db, page.id, kinds=["balloon"])
        approved_regions = text_regions

        # Use smart inpainting: balloon-aware fill for text inside balloons,
        # standard inpaint for floating text.
        inpainted = self._smart_inpaint(
            image,
            text_regions,
            balloon_regions,
            options=effective_options,
        )
        mask = self._build_mask(
            image.shape[:2],
            approved_regions,
            options=effective_options,
        )

        current_inpainted_file = await self.page_repo.get_current_file_by_kind(db, page.id, "inpainted")
        current_mask_file = await self.page_repo.get_current_file_by_kind(db, page.id, "inpaint_mask")
        reused_existing = self._is_same_as_current(
            generated_image=inpainted,
            generated_mask=mask,
            current_inpainted_file=current_inpainted_file,
            current_mask_file=current_mask_file,
        )
        if reused_existing:
            return {
                "approved_regions": len(approved_regions),
                "file_kind": "inpainted",
                "mask_file_kind": "inpaint_mask",
                "reused_existing": True,
                "inpaint_method": effective_options.method,
                "inpaint_radius": effective_options.radius,
                "text_expand_px": effective_options.text_expand_px,
            }

        source_suffix = ".png"
        image_relative_path = build_page_artifact_storage_path(
            str(page.chapter.project_id),
            str(page.chapter_id),
            str(page.id),
            "inpainted",
            f"page{source_suffix}",
        )
        mask_relative_path = build_page_artifact_storage_path(
            str(page.chapter.project_id),
            str(page.chapter_id),
            str(page.id),
            "inpainted",
            "erasure_mask.png",
        )
        output_path = resolve_storage_path(str(image_relative_path))

        await save_cv2_image(inpainted, image_relative_path)
        await save_cv2_image(mask, mask_relative_path)

        if current_inpainted_file is not None and current_mask_file is not None:
            overwrote_existing_files = True
            current_inpainted_file.pipeline_run_id = pipeline_run_id
            current_inpainted_file.file_path = str(image_relative_path)
            current_inpainted_file.mime_type = source_file.mime_type
            current_inpainted_file.width = int(inpainted.shape[1])
            current_inpainted_file.height = int(inpainted.shape[0])
            current_inpainted_file.is_current = True

            current_mask_file.pipeline_run_id = pipeline_run_id
            current_mask_file.file_path = str(mask_relative_path)
            current_mask_file.mime_type = "image/png"
            current_mask_file.width = int(mask.shape[1])
            current_mask_file.height = int(mask.shape[0])
            current_mask_file.is_current = True
        else:
            overwrote_existing_files = False
            await self.page_repo.mark_files_not_current(db, page_id=page.id, file_kind="inpainted")
            await self.page_repo.mark_files_not_current(db, page_id=page.id, file_kind="inpaint_mask")
            page_file = PageFile(
                page_id=page.id,
                pipeline_run_id=pipeline_run_id,
                file_kind="inpainted",
                file_path=str(image_relative_path),
                mime_type=source_file.mime_type,
                width=int(inpainted.shape[1]),
                height=int(inpainted.shape[0]),
                is_current=True,
            )
            await self.page_repo.create_file(db, page_file)
            mask_file = PageFile(
                page_id=page.id,
                pipeline_run_id=pipeline_run_id,
                file_kind="inpaint_mask",
                file_path=str(mask_relative_path),
                mime_type="image/png",
                width=int(mask.shape[1]),
                height=int(mask.shape[0]),
                is_current=True,
            )
            await self.page_repo.create_file(db, mask_file)

        return {
            "approved_regions": len(approved_regions),
            "file_kind": "inpainted",
            "mask_file_kind": "inpaint_mask",
            "reused_existing": False,
            "overwrote_existing_files": overwrote_existing_files,
            "storage_dir": str(output_path.parent),
            "inpaint_method": effective_options.method,
            "inpaint_radius": effective_options.radius,
            "text_expand_px": effective_options.text_expand_px,
        }
