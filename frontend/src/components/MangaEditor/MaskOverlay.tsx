import type { PointerEvent as ReactPointerEvent } from "react";

export interface MaskOverlayRegion {
  id: string;
  regionKind: string;
  displayPolygon: number[][];
  editablePolygon: number[][];
  readingOrderLabel?: string;
}

interface MaskOverlayProps {
  regions: MaskOverlayRegion[];
  naturalSize: { width: number; height: number } | null;
  visible: boolean;
  showLabels: boolean;
  interactive: boolean;
  showHandles: boolean;
  eraseMode?: boolean;
  activeMaskId?: string | null;
  isDragging?: boolean;
  drawingPoints?: number[][] | null;
  onOverlayPointerDown?: (event: ReactPointerEvent<SVGSVGElement>) => void;
  onOverlayPointerMove?: (event: ReactPointerEvent<SVGSVGElement>) => void;
  onOverlayPointerUp?: (event: ReactPointerEvent<SVGSVGElement>) => void;
  onOverlayPointerCancel?: (event: ReactPointerEvent<SVGSVGElement>) => void;
  onHandlePointerDown?: (
    event: ReactPointerEvent<SVGCircleElement>,
    regionId: string,
    pointIndex: number,
  ) => void;
  onPolygonPointerDown?: (
    event: ReactPointerEvent<SVGPolygonElement>,
    regionId: string,
  ) => void;
}

function maskColor(kind: string): { fill: string; stroke: string } {
  if (kind === "text") {
    return { fill: "rgba(56, 189, 248, 0.25)", stroke: "#0284C7" };
  }
  if (kind === "panel") {
    return { fill: "rgba(16, 185, 129, 0.20)", stroke: "#047857" };
  }
  if (kind === "balloon") {
    return { fill: "rgba(250, 204, 21, 0.22)", stroke: "#CA8A04" };
  }
  return { fill: "rgba(168, 85, 247, 0.20)", stroke: "#7E22CE" };
}

export default function MaskOverlay({
  regions,
  naturalSize,
  visible,
  showLabels,
  interactive,
  showHandles,
  eraseMode = false,
  activeMaskId = null,
  isDragging = false,
  drawingPoints = null,
  onOverlayPointerDown,
  onOverlayPointerMove,
  onOverlayPointerUp,
  onOverlayPointerCancel,
  onHandlePointerDown,
  onPolygonPointerDown,
}: MaskOverlayProps) {
  if (!naturalSize || (!visible && !drawingPoints)) {
    return null;
  }

  return (
    <svg
      className={`absolute inset-0 h-full w-full ${interactive ? "pointer-events-auto" : "pointer-events-none"}`}
      viewBox={`0 0 ${naturalSize.width} ${naturalSize.height}`}
      preserveAspectRatio="none"
      aria-label="Mask overlay"
      onPointerDown={onOverlayPointerDown}
      onPointerMove={onOverlayPointerMove}
      onPointerUp={onOverlayPointerUp}
      onPointerCancel={onOverlayPointerCancel}
      style={{ touchAction: isDragging ? "none" : "auto" }}
    >
      {drawingPoints && drawingPoints.length >= 2 && (
        <polygon
          points={drawingPoints.map(p => `${p[0]},${p[1]}`).join(" ")}
          fill="rgba(244, 197, 66, 0.3)"
          stroke="#F4C542"
          strokeWidth={2}
          strokeDasharray="4 4"
        />
      )}
      {regions.map((region) => {
        const colors = maskColor(region.regionKind);
        const polygonPoints = region.displayPolygon
          .map((point) => `${point[0]},${point[1]}`)
          .join(" ");
        const isActiveMask = activeMaskId === region.id;
        const isDraft = region.id.startsWith("temp-");
        const minX = Math.min(...region.displayPolygon.map((point) => point[0]));
        const minY = Math.min(...region.displayPolygon.map((point) => point[1]));

        return (
          <g 
            key={region.id}
            style={{ 
              opacity: isDraft ? 0.7 : 1,
              transition: "opacity 0.3s ease-in-out"
            }}
          >
            <polygon
              points={polygonPoints}
              fill={colors.fill}
              stroke={isActiveMask ? "#FF5C00" : colors.stroke}
              strokeWidth={isActiveMask ? 3 : 2}
              strokeDasharray={isDraft ? "5 5" : "none"}
              className={
                interactive
                  ? `mask-overlay-polygon ${eraseMode ? "cursor-not-allowed" : "cursor-move"}`
                  : ""
              }
              style={{ pointerEvents: interactive ? "auto" : "none" }}
              onPointerDown={
                interactive && onPolygonPointerDown
                  ? (event) => onPolygonPointerDown(event, region.id)
                  : undefined
              }
            />
            {
              // Only show handle circles for the active (selected) region to avoid
              // rendering dense circles for high-point user lassos which creates
              // the 'rope' visual. Also limit the number of visible handles by
              // sampling when the polygon has many points.
            }
            {(() => {
              const isActiveMask = activeMaskId === region.id;
              const SHOULD_SHOW_HANDLES = showHandles && isActiveMask;
              if (!SHOULD_SHOW_HANDLES) return null;

              const MAX_HANDLE_COUNT = 36;
              const pts = region.editablePolygon || [];
              let visiblePoints: number[][] = pts;
              if (pts.length > MAX_HANDLE_COUNT) {
                const step = Math.ceil(pts.length / MAX_HANDLE_COUNT);
                visiblePoints = pts.filter((_, i) => i % step === 0);
              }

              return visiblePoints.map((point, pointIndex) => (
                <circle
                  key={`${region.id}-point-${pointIndex}`}
                  cx={point[0]}
                  cy={point[1]}
                  r={3}
                  fill="rgba(255,255,255,0.95)"
                  stroke={colors.stroke}
                  strokeWidth={1.5}
                  className="mask-overlay-handle cursor-move"
                  style={{ pointerEvents: "auto" }}
                  onPointerDown={
                    onHandlePointerDown
                      ? (event) => onHandlePointerDown(event, region.id, pointIndex)
                      : undefined
                  }
                />
              ));
            })()}
            {showLabels && region.regionKind === "text" && region.readingOrderLabel ? (
              <g style={{ pointerEvents: "none" }}>
                <rect
                  x={Math.max(minX + 2, 0)}
                  y={Math.max(minY + 2, 0)}
                  rx={4}
                  ry={4}
                  width={42}
                  height={18}
                  fill="rgba(255, 255, 255, 0.92)"
                  stroke={colors.stroke}
                  strokeWidth={1}
                />
                <text
                  x={Math.max(minX + 23, 0)}
                  y={Math.max(minY + 14, 0)}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="700"
                  fill="#5C4D42"
                >
                  {region.readingOrderLabel}
                </text>
              </g>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
