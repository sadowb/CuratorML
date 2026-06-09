from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

import cv2
import numpy as np
from scipy import ndimage
from ultralytics import YOLO
from ultralytics.engine.results import Results

from app.core.config import settings

PANEL_DUPLICATE_IOU_THRESHOLD = 0.5
PANEL_NMS_SCORE_THRESHOLD = 0.0


class Detection(TypedDict):
    id: int
    region_kind: str
    box: list[float]
    conf: float
    mask: list[list[float]]


@lru_cache(maxsize=1)
def get_model() -> YOLO:
    return YOLO(str(settings.yolo_model_path_resolved))


def _bbox_from_polygon(polygon: list[list[float]]) -> list[float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return [min(xs), min(ys), max(xs), max(ys)]


def _rect_polygon_from_box(box: list[float]) -> tuple[list[list[float]], list[float]]:
    x1, y1, x2, y2 = [float(v) for v in box]
    polygon = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    return polygon, [x1, y1, x2, y2]


def _expand_box(box: list[float], padding_px: float) -> list[float]:
    x1, y1, x2, y2 = [float(v) for v in box]
    return [x1 - padding_px, y1 - padding_px, x2 + padding_px, y2 + padding_px]


def _apply_text_mask_dilation(detection: Detection) -> Detection:
    region_kind = detection["region_kind"]
    if region_kind not in {"text", "balloon"}:
        return detection

    box = detection["box"]
    width = max(float(box[2] - box[0]), 0.0)
    height = max(float(box[3] - box[1]), 0.0)
    dynamic_padding = max(width, height) * float(settings.text_box_padding_ratio)
    padding_px = max(float(settings.text_box_min_padding_px), dynamic_padding, 1.0)

    expanded_box = _expand_box(box, padding_px)
    return {
        **detection,
        "box": expanded_box,
    }


def _box_iou(box_a: list[float], box_b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
    bx1, by1, bx2, by2 = [float(v) for v in box_b]

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0.0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def _filter_duplicate_panels(detections: list[Detection]) -> list[Detection]:
    kept_panels: list[Detection] = []
    other_detections: list[Detection] = []

    panels = sorted(
        [d for d in detections if d["region_kind"] == "panel" and d["conf"] >= PANEL_NMS_SCORE_THRESHOLD],
        key=lambda item: item["conf"],
        reverse=True,
    )

    for panel in panels:
        is_duplicate = any(
            _box_iou(panel["box"], kept_panel["box"]) >= PANEL_DUPLICATE_IOU_THRESHOLD
            for kept_panel in kept_panels
        )
        if not is_duplicate:
            kept_panels.append(panel)

    for detection in detections:
        if detection["region_kind"] != "panel":
            other_detections.append(detection)

    return kept_panels + other_detections


def _collect_text_boxes_for_balloon(balloon_box: list[float], detections: list[Detection]) -> list[list[float]]:
    x1, y1, x2, y2 = [float(v) for v in balloon_box]
    pad = max(x2 - x1, y2 - y1) * float(settings.balloon_box_match_expand_ratio)
    x1 -= pad
    y1 -= pad
    x2 += pad
    y2 += pad

    matched: list[list[float]] = []
    for d in detections:
        if d["region_kind"] != "text":
            continue
        tx1, ty1, tx2, ty2 = [float(v) for v in d["box"]]
        cx = (tx1 + tx2) / 2.0
        cy = (ty1 + ty2) / 2.0
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            matched.append([tx1, ty1, tx2, ty2])
    return matched


def _mask_to_polygon(mask: np.ndarray, offset_x: int, offset_y: int) -> tuple[list[list[float]], list[float]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return [], [0.0, 0.0, 0.0, 0.0]

    contour = max(contours, key=cv2.contourArea)
    eps = max(1.0, 0.002 * cv2.arcLength(contour, True))
    contour = cv2.approxPolyDP(contour, eps, True)
    pts = contour.reshape(-1, 2)

    polygon = [[float(x + offset_x), float(y + offset_y)] for x, y in pts.tolist()]
    return polygon, _bbox_from_polygon(polygon)


def _repair_balloon_from_image(
    gray: np.ndarray,
    balloon_box: list[float],
    text_boxes: list[list[float]],
) -> tuple[list[list[float]], list[float]] | None:
    x1, y1, x2, y2 = [int(round(v)) for v in balloon_box]
    w = max(x2 - x1, 1)
    h = max(y2 - y1, 1)
    pad = max(6, int(round(max(w, h) * 0.08)))

    crop_x1 = max(0, x1 - pad)
    crop_y1 = max(0, y1 - pad)
    crop_x2 = min(gray.shape[1], x2 + pad)
    crop_y2 = min(gray.shape[0], y2 + pad)

    crop = gray[crop_y1:crop_y2, crop_x1:crop_x2]
    if crop.size == 0:
        return None

    ink = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    k = max(3, int(round(max(crop.shape[:2]) * 0.03)))
    if k % 2 == 0:
        k += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    # Close small gaps in the balloon outline so flood/CC does not leak outside.
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel)

    # White regions inside the bubble become traversable.
    free = (ink == 0).astype(np.uint8)

    # Seed from text boxes. If none, use the bbox center.
    seed = np.zeros_like(free, dtype=np.uint8)
    if text_boxes:
        for tx1, ty1, tx2, ty2 in text_boxes:
            sx1 = max(0, int(round(tx1)) - crop_x1)
            sy1 = max(0, int(round(ty1)) - crop_y1)
            sx2 = min(free.shape[1] - 1, int(round(tx2)) - crop_x1)
            sy2 = min(free.shape[0] - 1, int(round(ty2)) - crop_y1)
            cv2.rectangle(seed, (sx1, sy1), (sx2, sy2), 255, -1)
    else:
        cx = min(max((x1 + x2) // 2 - crop_x1, 0), free.shape[1] - 1)
        cy = min(max((y1 + y2) // 2 - crop_y1, 0), free.shape[0] - 1)
        cv2.circle(seed, (cx, cy), 3, 255, -1)

    seed = cv2.dilate(seed, np.ones((5, 5), dtype=np.uint8), iterations=1)

    num_labels, labels = cv2.connectedComponents(free)
    if num_labels <= 1:
        return None

    seed_labels = labels[(seed > 0) & (free > 0)]
    seed_labels = seed_labels[seed_labels > 0]
    if seed_labels.size == 0:
        return None

    chosen = int(np.bincount(seed_labels).argmax())
    balloon = (labels == chosen).astype(np.uint8)

    # If the selected region touches the crop border, it probably leaked outside.
    if balloon[0].any() or balloon[-1].any() or balloon[:, 0].any() or balloon[:, -1].any():
        return None

    balloon = ndimage.binary_fill_holes(balloon).astype(np.uint8)
    balloon = cv2.morphologyEx(balloon * 255, cv2.MORPH_CLOSE, kernel)

    polygon, bbox = _mask_to_polygon(balloon, crop_x1, crop_y1)
    if len(polygon) < 3:
        return None

    return polygon, bbox


def extract_detections(result: Results) -> list[Detection]:
    detections: list[Detection] = []
    if result.boxes is None:
        return detections

    boxes = result.boxes.xyxy.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    masks = result.masks.xy if result.masks is not None else None

    class_map = {0: "panel", 1: "text", 2: "balloon"}

    for idx in range(len(boxes)):
        cls_id = int(classes[idx])
        if cls_id not in class_map:
            continue

        region_kind = class_map[cls_id]
        box = [float(v) for v in boxes[idx]]

        if masks is not None and idx < len(masks) and len(masks[idx]) > 0:
            mask_polygon = [[float(x), float(y)] for x, y in masks[idx]]
            final_box = box
        elif region_kind == "text" and settings.text_use_detection_box:
            mask_polygon, final_box = _rect_polygon_from_box(box)
        else:
            mask_polygon, final_box = _rect_polygon_from_box(box)

        detections.append(
            {
                "id": idx,
                "region_kind": region_kind,
                "box": final_box,
                "conf": float(confs[idx]),
                "mask": mask_polygon,
            }
        )

    detections = [_apply_text_mask_dilation(detection) for detection in detections]
    return _filter_duplicate_panels(detections)


def postprocess_mask_detections(detections: list[Detection], gray: np.ndarray) -> list[Detection]:
    out: list[Detection] = []

    for detection in detections:
        if detection["region_kind"] != "balloon" or not settings.balloon_repair_enabled:
            out.append(detection)
            continue

        text_boxes = _collect_text_boxes_for_balloon(detection["box"], detections)
        repaired = _repair_balloon_from_image(gray, detection["box"], text_boxes)

        if repaired is None:
            out.append(detection)
        else:
            polygon, bbox = repaired
            out.append({**detection, "mask": polygon, "box": bbox})

    return out


def run_inference(image_path: str) -> list[Detection]:
    model = get_model()
    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return []

    predict_kwargs = {
        "source": image_path,
        "conf": settings.yolo_confidence_threshold,
        "iou": settings.yolo_iou_threshold,
        "imgsz": settings.yolo_inference_size,
        "max_det": settings.yolo_max_detections,
        "retina_masks": True,
        "verbose": False,
    }
    if settings.yolo_device != "auto":
        predict_kwargs["device"] = settings.yolo_device

    results: list[Results] = model.predict(**predict_kwargs)

    if not results:
        return []

    detections = extract_detections(results[0])
    return postprocess_mask_detections(detections, gray)
