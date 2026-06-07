import { useCallback, useMemo, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

interface OverlayRegionGeometry {
  id: string;
  regionKind: string;
  editablePolygon: number[][];
}

type OverlayInteractionMode = "select" | "erase" | "pen" | "none";
type PenShape = "box" | "polygon";

interface UseMaskOverlayInteractionsParams {
  mode: OverlayInteractionMode;
  penShape?: PenShape;
  naturalSize: { width: number; height: number } | null;
  regions: OverlayRegionGeometry[];
  onRegionPolygonChange?: (regionId: string, polygon: number[][]) => void;
  onRegionSelect?: (regionId: string) => void;
  onRegionDelete?: (regionId: string) => void;
  onRegionCreate?: (polygon: number[][]) => void;
}

type DragState =
  | {
    type: "vertex";
    regionId: string;
    pointIndex: number;
  }
  | {
    type: "polygon";
    regionId: string;
    startPoint: [number, number];
    originalPolygon: number[][];
  }
  | {
    type: "drawing";
    shape: PenShape;
    startPoint: [number, number];
    points: number[][];
  };

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function toRectPolygon(
  a: [number, number],
  b: [number, number],
): number[][] {
  const x1 = Math.min(a[0], b[0]);
  const y1 = Math.min(a[1], b[1]);
  const x2 = Math.max(a[0], b[0]);
  const y2 = Math.max(a[1], b[1]);
  return [
    [x1, y1],
    [x2, y1],
    [x2, y2],
    [x1, y2],
  ];
}

export function useMaskOverlayInteractions({
  mode,
  penShape,
  naturalSize,
  regions,
  onRegionPolygonChange,
  onRegionSelect,
  onRegionDelete,
  onRegionCreate,
}: UseMaskOverlayInteractionsParams) {
  const [dragState, setDragState] = useState<DragState | null>(null);

  const editablePolygonByRegionId = useMemo(() => {
    const map = new Map<string, number[][]>();
    for (const region of regions) {
      map.set(region.id, region.editablePolygon);
    }
    return map;
  }, [regions]);

  const regionKindByRegionId = useMemo(() => {
    const map = new Map<string, string>();
    for (const region of regions) {
      map.set(region.id, region.regionKind);
    }
    return map;
  }, [regions]);

  const resolveSvgPoint = useCallback(
    (
      clientX: number,
      clientY: number,
      element: SVGSVGElement | SVGElement,
    ): [number, number] | null => {
      if (!naturalSize) {
        return null;
      }
      const svgElement =
        "ownerSVGElement" in element && element.ownerSVGElement
          ? element.ownerSVGElement
          : (element as SVGSVGElement);
      const rect = svgElement.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        return null;
      }
      const x = ((clientX - rect.left) / rect.width) * naturalSize.width;
      const y = ((clientY - rect.top) / rect.height) * naturalSize.height;
      return [clamp(x, 0, naturalSize.width), clamp(y, 0, naturalSize.height)];
    },
    [naturalSize],
  );

  const onOverlayPointerDown = useCallback(
    (event: ReactPointerEvent<SVGSVGElement>) => {
      if (mode !== "pen") return;

      const point = resolveSvgPoint(event.clientX, event.clientY, event.currentTarget);
      if (!point) return;

      event.preventDefault();
      event.stopPropagation();
      const target = event.currentTarget;
      if (typeof target.setPointerCapture === "function") {
        target.setPointerCapture(event.pointerId);
      }

      const roundedPoint: [number, number] = [
        Math.round(point[0] * 10) / 10,
        Math.round(point[1] * 10) / 10
      ];

      setDragState({
        type: "drawing",
        shape: penShape || "box",
        startPoint: roundedPoint,
        points: [roundedPoint],
      });
    },
    [mode, penShape, resolveSvgPoint]
  );

  const onOverlayPointerMove = useCallback(
    (event: ReactPointerEvent<SVGSVGElement>) => {
      if (!dragState) return;
      if (mode !== "select" && mode !== "pen") return;

      const nextPoint = resolveSvgPoint(
        event.clientX,
        event.clientY,
        event.currentTarget,
      );
      if (!nextPoint) return;

      if (dragState.type === "drawing") {
        const roundedPoint: [number, number] = [
          Math.round(nextPoint[0] * 10) / 10,
          Math.round(nextPoint[1] * 10) / 10
        ];

        if (dragState.shape === "box") {
          const polygon = toRectPolygon(dragState.startPoint, roundedPoint);
          setDragState({ ...dragState, points: polygon });
        } else {
          // Lasso/Polygon drawing: accumulate points with smoothing
          setDragState((prev) => {
            if (!prev || prev.type !== "drawing") return prev;
            const lastPoint = prev.points[prev.points.length - 1];
            if (!lastPoint) return prev;

            const dist = Math.sqrt(
              Math.pow(roundedPoint[0] - lastPoint[0], 2) +
              Math.pow(roundedPoint[1] - lastPoint[1], 2)
            );

            // Only add point if it moved significantly (4px threshold)
            if (dist < 4) return prev;
            return { ...prev, points: [...prev.points, roundedPoint] };
          });
        }
        return;
      }

      if (mode !== "select" || !onRegionPolygonChange) return;

      if (dragState.type === "vertex") {
        const polygon = editablePolygonByRegionId.get(dragState.regionId);
        if (!polygon || polygon.length < 3) {
          return;
        }

        const regionKind = regionKindByRegionId.get(dragState.regionId);
        if (regionKind === "text" && polygon.length === 4) {
          // Keep text regions as axis-aligned containers instead of arbitrary quads.
          const oppositeIndex = (dragState.pointIndex + 2) % 4;
          const oppositePoint = polygon[oppositeIndex] as [number, number];
          const nextPolygon = toRectPolygon(oppositePoint, nextPoint);
          onRegionPolygonChange(dragState.regionId, nextPolygon);
          return;
        }

        const nextPolygon = [...polygon];
        nextPolygon[dragState.pointIndex] = nextPoint;
        onRegionPolygonChange(dragState.regionId, nextPolygon);
        return;
      }

      if (dragState.type === "polygon") {
        if (!naturalSize || dragState.originalPolygon.length < 3) {
          return;
        }

        const deltaX = nextPoint[0] - dragState.startPoint[0];
        const deltaY = nextPoint[1] - dragState.startPoint[1];
        const xs = dragState.originalPolygon.map((point) => point[0]);
        const ys = dragState.originalPolygon.map((point) => point[1]);
        const minX = Math.min(...xs);
        const maxX = Math.max(...xs);
        const minY = Math.min(...ys);
        const maxY = Math.max(...ys);
        const boundedDeltaX = clamp(deltaX, -minX, naturalSize.width - maxX);
        const boundedDeltaY = clamp(deltaY, -minY, naturalSize.height - maxY);
        const nextPolygon = dragState.originalPolygon.map(([x, y]) => [
          x + boundedDeltaX,
          y + boundedDeltaY,
        ]);

        onRegionPolygonChange(dragState.regionId, nextPolygon);
      }
    },
    [
      dragState,
      mode,
      editablePolygonByRegionId,
      regionKindByRegionId,
      naturalSize,
      onRegionPolygonChange,
      resolveSvgPoint,
    ],
  );

  const stopDragging = useCallback(() => {
    if (dragState) {
      if (dragState.type === "drawing" && dragState.points.length >= 3 && onRegionCreate) {
        onRegionCreate(dragState.points);
      }
      setDragState(null);
    }
  }, [dragState, onRegionCreate]);

  const onHandlePointerDown = useCallback(
    (
      event: ReactPointerEvent<SVGCircleElement>,
      regionId: string,
      pointIndex: number,
    ) => {
      if (mode !== "select") {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const target = event.currentTarget;
      if (typeof target.setPointerCapture === "function") {
        target.setPointerCapture(event.pointerId);
      }
      setDragState({ type: "vertex", regionId, pointIndex });
      onRegionSelect?.(regionId);
    },
    [mode, onRegionSelect],
  );

  const onPolygonPointerDown = useCallback(
    (event: ReactPointerEvent<SVGPolygonElement>, regionId: string) => {
      if (mode === "none") {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      onRegionSelect?.(regionId);

      if (mode === "erase") {
        onRegionDelete?.(regionId);
        return;
      }

      const polygon = editablePolygonByRegionId.get(regionId);
      const startPoint = resolveSvgPoint(
        event.clientX,
        event.clientY,
        event.currentTarget,
      );
      if (!polygon || polygon.length < 3 || !startPoint) {
        return;
      }

      const target = event.currentTarget;
      if (typeof target.setPointerCapture === "function") {
        target.setPointerCapture(event.pointerId);
      }

      setDragState({
        type: "polygon",
        regionId,
        startPoint,
        originalPolygon: polygon.map(([x, y]) => [x, y]),
      });
    },
    [
      editablePolygonByRegionId,
      mode,
      onRegionDelete,
      onRegionSelect,
      resolveSvgPoint,
    ],
  );

  return {
    isDragging: Boolean(dragState),
    drawingPoints: dragState?.type === "drawing" ? dragState.points : null,
    onOverlayPointerDown,
    onOverlayPointerMove,
    onOverlayPointerUp: stopDragging,
    onOverlayPointerCancel: stopDragging,
    onHandlePointerDown,
    onPolygonPointerDown,
  };
}
