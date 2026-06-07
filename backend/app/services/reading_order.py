from __future__ import annotations

import heapq
import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from app.models.page_region import PageRegion

logger = logging.getLogger("manga_api.reading_order")

# Tuneable constants
SAME_ROW_THRESHOLD: float = 0.10
SAME_COL_THRESHOLD: float = 0.10
ROW_GAP_FACTOR: float = 0.55
MIN_ROW_GAP_PX: float = 12.0
DOUBLE_PAGE_MIN_ASPECT_RATIO: float = 1.2
DOUBLE_PAGE_MAX_CROSSING_RATIO: float = 0.25
DOUBLE_PAGE_HUGE_PANEL_RATIO: float = 0.60

# Mask quality constants
_MIN_MASK_POINTS: int = 3
_MIN_MASK_COVERAGE: float = 0.20


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def area(self) -> float:
        return self.width * self.height

    def contains_point(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def intersection(self, other: "Box") -> Optional["Box"]:
        x1 = max(self.x1, other.x1)
        y1 = max(self.y1, other.y1)
        x2 = min(self.x2, other.x2)
        y2 = min(self.y2, other.y2)
        return Box(x1, y1, x2, y2) if x1 < x2 and y1 < y2 else None

    def iou(self, other: "Box") -> float:
        inter = self.intersection(other)
        if inter is None:
            return 0.0
        union = self.area + other.area - inter.area
        return inter.area / union if union > 0.0 else 0.0

    def vertical_overlap_ratio(self, other: "Box") -> float:
        overlap = max(0.0, min(self.y2, other.y2) - max(self.y1, other.y1))
        shorter = min(self.height, other.height)
        return overlap / shorter if shorter > 0.0 else 0.0

    def horizontal_overlap_ratio(self, other: "Box") -> float:
        overlap = max(0.0, min(self.x2, other.x2) - max(self.x1, other.x1))
        narrower = min(self.width, other.width)
        return overlap / narrower if narrower > 0.0 else 0.0

    def center_distance(self, other: "Box") -> float:
        return math.hypot(self.cx - other.cx, self.cy - other.cy)

    @classmethod
    def from_list(cls, coords: Sequence[float]) -> "Box":
        x1, y1, x2, y2 = coords
        return cls(float(x1), float(y1), float(x2), float(y2))


def _polygon_area(pts: np.ndarray) -> float:
    x = pts[:, 0]
    y = pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def _polygon_centroid(pts: np.ndarray) -> Tuple[float, float]:
    area = _polygon_area(pts)
    if area < 1e-6:
        return float(pts[:, 0].mean()), float(pts[:, 1].mean())

    x = pts[:, 0]
    y = pts[:, 1]
    x_next = np.roll(x, -1)
    y_next = np.roll(y, -1)
    cross = x * y_next - x_next * y
    cx = float(np.sum((x + x_next) * cross) / (6.0 * area))
    cy = float(np.sum((y + y_next) * cross) / (6.0 * area))
    return cx, cy


@dataclass
class ReadingRegion:
    """Wraps a `PageRegion` with convenient geometry helpers."""

    region: PageRegion
    box: Box
    kind: str
    mask: list  # polygon vertices or empty
    conf: float | None = None

    @property
    def id(self):
        return self.region.id

    @property
    def has_valid_mask(self) -> bool:
        if not self.mask or len(self.mask) < _MIN_MASK_POINTS:
            return False
        pts = np.array(self.mask, dtype=float)
        poly_area = _polygon_area(pts)
        box_area = self.box.area
        if box_area < 1.0:
            return False
        return (poly_area / box_area) >= _MIN_MASK_COVERAGE

    @property
    def mask_centroid(self) -> Optional[Tuple[float, float]]:
        if not self.has_valid_mask:
            return None
        pts = np.array(self.mask, dtype=float)
        return _polygon_centroid(pts)

    @property
    def effective_center(self) -> Tuple[float, float]:
        centroid = self.mask_centroid
        if centroid is not None:
            cx, cy = centroid
            if self.box.contains_point(cx, cy):
                return cx, cy
        return self.box.cx, self.box.cy

    @property
    def reading_score(self) -> float:
        # Right-most and top-most score highest (manga RTL ordering)
        return self.box.cx - self.box.cy * 10.0


@dataclass
class BalloonGroup:
    balloon: ReadingRegion
    texts: List[ReadingRegion]


@dataclass
class PanelGroup:
    panel: ReadingRegion
    balloons: List[BalloonGroup]
    orphan_texts: List[ReadingRegion]


def _reading_order_edge(a: ReadingRegion, b: ReadingRegion) -> Optional[Tuple]:
    v_ratio = a.box.vertical_overlap_ratio(b.box)
    h_ratio = a.box.horizontal_overlap_ratio(b.box)

    is_same_row = v_ratio > SAME_ROW_THRESHOLD
    is_same_col = h_ratio > SAME_COL_THRESHOLD

    if not is_same_row and not is_same_col:
        return None

    if is_same_row and not is_same_col:
        first, second = (a, b) if a.box.cx > b.box.cx else (b, a)
    elif is_same_col and not is_same_row:
        first, second = (a, b) if a.box.cy < b.box.cy else (b, a)
    else:
        if v_ratio >= h_ratio:
            first, second = (a, b) if a.box.cx > b.box.cx else (b, a)
        else:
            first, second = (a, b) if a.box.cy < b.box.cy else (b, a)

    return (first.id, second.id)


def _build_panel_dag(panels: List[ReadingRegion]) -> dict:
    dependencies: dict = {p.id: set() for p in panels}
    for i, a in enumerate(panels):
        for b in panels[i + 1:]:
            edge = _reading_order_edge(a, b)
            if edge is not None:
                pred, succ = edge
                dependencies[succ].add(pred)
    return dependencies


def _topological_sort(panels: List[ReadingRegion], dependencies: dict) -> List[ReadingRegion]:
    panel_by_id = {p.id: p for p in panels}
    successors: dict = defaultdict(list)
    in_degree: dict = {}

    for panel_id, deps in dependencies.items():
        in_degree[panel_id] = len(deps)
        for dep_id in deps:
            successors[dep_id].append(panel_id)

    heap: List[Tuple[float, object]] = [(-panel.reading_score, panel.id) for panel in panels if in_degree.get(panel.id, 0) == 0]
    heapq.heapify(heap)

    sorted_panels: List[ReadingRegion] = []
    while heap:
        _, pid = heapq.heappop(heap)
        sorted_panels.append(panel_by_id[pid])
        for succ in successors.get(pid, []):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                succ_region = panel_by_id[succ]
                heapq.heappush(heap, (-succ_region.reading_score, succ))

    if len(sorted_panels) != len(panels):
        resolved_ids = {p.id for p in sorted_panels}
        unresolved = [p for p in panels if p.id not in resolved_ids]
        logger.warning(
            "Cycle detected in panel DAG — %d panel(s) could not be topologically sorted. Appending them by reading_score.",
            len(unresolved),
        )
        unresolved.sort(key=lambda p: -p.reading_score)
        sorted_panels.extend(unresolved)

    return sorted_panels


def _find_parent_panel(item: ReadingRegion, panels: List[ReadingRegion]) -> Optional[ReadingRegion]:
    cx, cy = item.effective_center
    panels_containing = [p for p in panels if p.box.contains_point(cx, cy)]
    if len(panels_containing) == 1:
        return panels_containing[0]
    if len(panels_containing) > 1:
        return max(panels_containing, key=lambda p: p.box.iou(item.box))
    if panels:
        return min(panels, key=lambda p: p.box.center_distance(item.box))
    return None


def _assign_items_to_panels(panels: List[ReadingRegion], items: List[ReadingRegion]) -> dict:
    groups: dict = defaultdict(list)
    for item in items:
        parent = _find_parent_panel(item, panels)
        if parent is None:
            logger.warning("Region id=%s kind=%s could not be assigned to any panel.", item.id, item.kind)
            groups[-1].append(item)
        else:
            groups[parent.id].append(item)
    return groups


def _cluster_into_rows(items: List[ReadingRegion]) -> List[List[ReadingRegion]]:
    if not items:
        return []
    items_by_y = sorted(items, key=lambda r: r.effective_center[1])
    heights = np.array([r.box.height for r in items_by_y], dtype=float)
    row_threshold = max(MIN_ROW_GAP_PX, float(np.median(heights)) * ROW_GAP_FACTOR)
    rows: List[List[ReadingRegion]] = [[items_by_y[0]]]
    for current in items_by_y[1:]:
        last_cy = rows[-1][-1].effective_center[1]
        cur_cy = current.effective_center[1]
        gap = cur_cy - last_cy
        if gap <= row_threshold:
            rows[-1].append(current)
        else:
            rows.append([current])
    return rows


def _sort_within_panel(items: List[ReadingRegion]) -> List[ReadingRegion]:
    rows = _cluster_into_rows(items)
    ordered: List[ReadingRegion] = []
    for row in rows:
        right_to_left = sorted(row, key=lambda r: r.effective_center[0], reverse=True)
        ordered.extend(right_to_left)
    return ordered


def _is_likely_double_page_spread(image_shape: tuple[int, int]) -> bool:
    height, width = image_shape
    if height <= 0 or width <= 0:
        return False
    return (width / height) >= DOUBLE_PAGE_MIN_ASPECT_RATIO


def _partition_panels_for_double_page_spread(
    panels: List[ReadingRegion],
    image_shape: tuple[int, int],
) -> Optional[Tuple[List[ReadingRegion], List[ReadingRegion]]]:
    """
    Detects two-page spreads and splits panels into (right_page, left_page).

    We intentionally avoid splitting when a large panel crosses the center seam,
    because that usually means the page should be treated as one composition.
    """
    if len(panels) < 2 or not _is_likely_double_page_spread(image_shape):
        return None

    min_x = min(panel.box.x1 for panel in panels)
    max_x = max(panel.box.x2 for panel in panels)
    span = max_x - min_x
    if span <= 0.0:
        return None

    seam_x = min_x + (span / 2.0)
    crossing = [panel for panel in panels if panel.box.x1 < seam_x < panel.box.x2]
    if crossing:
        if any((panel.box.width / span) >= DOUBLE_PAGE_HUGE_PANEL_RATIO for panel in crossing):
            return None
        if (len(crossing) / len(panels)) > DOUBLE_PAGE_MAX_CROSSING_RATIO:
            return None

    right_page = [panel for panel in panels if panel.box.cx >= seam_x]
    left_page = [panel for panel in panels if panel.box.cx < seam_x]
    if not right_page or not left_page:
        return None

    return right_page, left_page


def build_reading_order(page_regions: Sequence[PageRegion], image_shape: tuple[int, int]) -> List[PanelGroup]:
    # Convert PageRegion -> ReadingRegion
    adapted: List[ReadingRegion] = []
    for pr in page_regions:
        # derive box from bbox_json or polygon_json
        box = None
        if pr.bbox_json and isinstance(pr.bbox_json, list) and len(pr.bbox_json) == 4:
            box = Box.from_list(pr.bbox_json)
        elif pr.bbox_json and isinstance(pr.bbox_json, dict):
            # support dict formats
            if {"x1", "y1", "x2", "y2"}.issubset(pr.bbox_json):
                coords = [pr.bbox_json["x1"], pr.bbox_json["y1"], pr.bbox_json["x2"], pr.bbox_json["y2"]]
                box = Box.from_list(coords)
            elif {"left", "top", "right", "bottom"}.issubset(pr.bbox_json):
                coords = [pr.bbox_json["left"], pr.bbox_json["top"], pr.bbox_json["right"], pr.bbox_json["bottom"]]
                box = Box.from_list(coords)
        elif pr.polygon_json:
            try:
                xs = [float(p[0]) for p in pr.polygon_json]
                ys = [float(p[1]) for p in pr.polygon_json]
                box = Box(min(xs), min(ys), max(xs), max(ys))
            except Exception:
                box = None

        if box is None:
            continue

        mask = pr.polygon_json if pr.polygon_json else []
        kind = pr.region_kind
        adapted.append(ReadingRegion(region=pr, box=box, kind=kind, mask=mask, conf=pr.confidence))

    panels = [r for r in adapted if r.kind == "panel"]
    balloons = [r for r in adapted if r.kind == "balloon"]
    texts = [r for r in adapted if r.kind == "text"]

    if not panels:
        logger.warning("No panels detected on this page — returning empty result.")
        return []

    spread_partitions = _partition_panels_for_double_page_spread(panels, image_shape)
    if spread_partitions is None:
        dependencies = _build_panel_dag(panels)
        ordered_panels = _topological_sort(panels, dependencies)
    else:
        right_page, left_page = spread_partitions
        right_dependencies = _build_panel_dag(right_page)
        left_dependencies = _build_panel_dag(left_page)
        # Manga default: read the right page, then the left page.
        ordered_panels = _topological_sort(right_page, right_dependencies) + _topological_sort(left_page, left_dependencies)

    panel_to_balloons = _assign_items_to_panels(ordered_panels, balloons)
    panel_to_texts = _assign_items_to_panels(ordered_panels, texts)

    panel_groups: List[PanelGroup] = []
    for panel in ordered_panels:
        # Sort balloons within panel
        raw_balloons = panel_to_balloons.get(panel.id, [])
        sorted_balloons = _sort_within_panel(raw_balloons)

        raw_texts = panel_to_texts.get(panel.id, [])

        text_to_balloon = defaultdict(list)
        orphan_texts = []

        for text in raw_texts:
            assigned = False
            if sorted_balloons:
                cx, cy = text.effective_center
                containing = [b for b in sorted_balloons if b.box.contains_point(cx, cy)]
                if len(containing) == 1:
                    text_to_balloon[containing[0].id].append(text)
                    assigned = True
                elif len(containing) > 1:
                    best = max(containing, key=lambda b: b.box.iou(text.box))
                    text_to_balloon[best.id].append(text)
                    assigned = True
                else:
                    # Not strictly containing the center. Check overlap.
                    overlapping = [b for b in sorted_balloons if b.box.iou(text.box) > 0.05]
                    if overlapping:
                        best = max(overlapping, key=lambda b: b.box.iou(text.box))
                        text_to_balloon[best.id].append(text)
                        assigned = True
            
            if not assigned:
                orphan_texts.append(text)

        balloon_groups: List[BalloonGroup] = []
        for balloon in sorted_balloons:
            # Sort texts within balloon
            bt = text_to_balloon.get(balloon.id, [])
            sorted_texts = _sort_within_panel(bt)
            balloon_groups.append(BalloonGroup(balloon=balloon, texts=sorted_texts))

        # Sort orphan texts in panel
        sorted_orphans = _sort_within_panel(orphan_texts)

        panel_groups.append(PanelGroup(panel=panel, balloons=balloon_groups, orphan_texts=sorted_orphans))

    return panel_groups
