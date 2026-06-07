import type { PageRegion } from "../../../types/api";
import type { MaskRegionFilter } from "../maskEditorTypes";

export const MAX_EDITABLE_POINTS = 5;

export function isEditablePolygon(
  polygon: number[][] | null | undefined,
): polygon is number[][] {
  return (
    Array.isArray(polygon) &&
    polygon.length > 2 &&
    polygon.every((point) => point.length >= 2)
  );
}

export function deriveBbox(polygon: number[][]): number[] {
  const xs = polygon.map((p) => p[0]);
  const ys = polygon.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

export function bboxToPolygon(bbox: number[] | null | undefined): number[][] | null {
  if (!bbox || bbox.length !== 4) return null;
  const [x1, y1, x2, y2] = bbox;
  return [
    [x1, y1],
    [x2, y1],
    [x2, y2],
    [x1, y2],
  ];
}

export function simplifyPolygon(
  polygon: number[][],
  bbox: number[] | null,
): number[][] {
  if (polygon.length <= MAX_EDITABLE_POINTS) return polygon;

  const sampled: number[][] = [];
  const last = polygon.length - 1;
  for (let i = 0; i < MAX_EDITABLE_POINTS; i++) {
    sampled.push(polygon[Math.round((i * last) / (MAX_EDITABLE_POINTS - 1))]);
  }
  if (sampled.length >= 3) return sampled;
  return bboxToPolygon(bbox) ?? polygon;
}

export function buildEditableMap(regions: PageRegion[]): Record<string, number[][]> {
  const map: Record<string, number[][]> = {};
  for (const r of regions) {
    if (r.region_kind === "text") {
      // Hybrid Logic: For text, ONLY use the polygon if it's 'User Verified' (confidence >= 1).
      // AI text (confidence < 1) always renders as a clean box.
      if ((r.confidence ?? 0) >= 1.0 && isEditablePolygon(r.polygon_json)) {
        // Preserve full manual/user-created polygons to keep precise lasso shapes.
        const origin = (r.origin || "").toString().toLowerCase();
        if (origin === "user_edited") {
          map[r.id] = r.polygon_json as number[][];
        } else {
          map[r.id] = simplifyPolygon(r.polygon_json, r.bbox_json);
        }
      } else {
        const textBoxPolygon = bboxToPolygon(r.bbox_json);
        if (isEditablePolygon(textBoxPolygon)) {
          map[r.id] = textBoxPolygon;
        }
      }
      continue;
    }

    if (isEditablePolygon(r.polygon_json)) {
      const origin = (r.origin || "").toString().toLowerCase();
      if (origin === "user_edited") {
        map[r.id] = r.polygon_json as number[][];
      } else {
        map[r.id] = simplifyPolygon(r.polygon_json, r.bbox_json);
      }
    }
  }
  return map;
}

export function applyFilter(
  regions: PageRegion[],
  filter: MaskRegionFilter,
): PageRegion[] {
  if (filter.mode === "all") return regions;
  return regions.filter((r) => r.region_kind === filter.regionKind);
}
