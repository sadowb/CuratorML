import {
  TransformComponent,
  TransformWrapper,
  useControls,
  useTransformComponent,
} from "react-zoom-pan-pinch";
import { useMemo, useState, useEffect, useRef, useCallback } from "react";
import { layoutWithLines, prepareWithSegments } from "@chenglou/pretext";
import FloatingToolRail from "./FloatingToolRail";
import MaskOverlay from "./MaskOverlay";
import { useMaskOverlayInteractions } from "../../hooks/editor/useMaskOverlayInteractions";
import { useImagePreload } from "../../hooks/useImagePreload";
import type {
  TypographyStyle,
  WorkspaceMaskController,
} from "../../hooks/editor/maskEditorTypes";
import type { PageRegion, PageText } from "../../types/api";
import { cn } from "../../lib/utils";
import { resolveTranslatedText } from "../../lib/textDisplay";
import { useEditorStore } from "../../store/useEditorStore";
import { savePageInpaintCleanup } from "../../lib/api/pages";

interface WorkspaceProps {
  imageUrl?: string;
  isInpaintedView?: boolean;
  pageId?: string;
  maskController: WorkspaceMaskController;
  selectedTextRegionId?: string | null;
  onTextRegionSelect?: (regionId: string) => void;
  readingOrderLabelsByRegionId?: Record<string, string>;
  texts?: PageText[];
  showTranslatedText?: boolean;
  textScaleByTextId?: Record<string, number>;
  onTextRegionManualPlacement?: (regionId: string) => void;
  onRenderBoundsChange?: (textId: string, bounds: [number, number, number, number]) => void;
  onInpaintedImageSaved?: () => Promise<void> | void;
}

// Bounding box utility for fallback text container derivation
function getRegionBbox(region?: { bbox_json?: number[] | null; polygon_json?: number[][] | null }): number[] | null {
  if (!region) return null;
  if (Array.isArray(region.bbox_json) && region.bbox_json.length === 4) return region.bbox_json;
  if (Array.isArray(region.polygon_json) && region.polygon_json.length) {
    const xs = region.polygon_json.map((p) => p[0]), ys = region.polygon_json.map((p) => p[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  return null;
}

function bboxToPolygon(b: number[] | null): number[][] {
  return b ? [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]] : [];
}

function bboxArea(bbox: number[] | null): number {
  if (!bbox) return 0;
  return Math.max(0, bbox[2] - bbox[0]) * Math.max(0, bbox[3] - bbox[1]);
}

function bboxIoU(a: number[] | null, b: number[] | null): number {
  if (!a || !b) return 0;
  const x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]);
  const x2 = Math.min(a[2], b[2]), y2 = Math.min(a[3], b[3]);
  const interArea = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  if (interArea <= 0) return 0;
  const union = bboxArea(a) + bboxArea(b) - interArea;
  return union > 0 ? interArea / union : 0;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function pointInPolygon(point: [number, number], polygon: number[][] | null | undefined): boolean {
  if (!polygon || polygon.length < 3) return false;
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0];
    const yi = polygon[i][1];
    const xj = polygon[j][0];
    const yj = polygon[j][1];
    const intersects = ((yi > y) !== (yj > y)) && (x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-9) + xi);
    if (intersects) inside = !inside;
  }
  return inside;
}

// Ray-cast algorithm to find exact horizontal span of a polygon at a given Y coordinate
function getPolygonHorizontalWidthAtY(polygon: number[][] | null | undefined, y: number): [number, number] | null {
  if (!polygon || polygon.length < 3) return null;
  let minX = Infinity;
  let maxX = -Infinity;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const p1 = polygon[i];
    const p2 = polygon[j];
    if ((p1[1] > y) !== (p2[1] > y)) {
      const intersectX = p1[0] + ((y - p1[1]) * (p2[0] - p1[0])) / (p2[1] - p1[1]);
      minX = Math.min(minX, intersectX);
      maxX = Math.max(maxX, intersectX);
    }
  }
  return minX === Infinity ? null : [minX, maxX];
}

function toCanvasPoint(
  event: React.PointerEvent<HTMLCanvasElement>,
  naturalSize: { width: number; height: number },
): [number, number] {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * naturalSize.width;
  const y = ((event.clientY - rect.top) / rect.height) * naturalSize.height;
  return [clamp(x, 0, naturalSize.width), clamp(y, 0, naturalSize.height)];
}

// Minimal hook to observe viewport constraint resizing
function useViewportSize(ref: React.RefObject<HTMLDivElement | null>) {
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  useEffect(() => {
    const update = () => ref.current && setSize({ width: ref.current.clientWidth, height: ref.current.clientHeight });
    update();
    if (ref.current && typeof ResizeObserver === "function") {
      const o = new ResizeObserver(update);
      o.observe(ref.current);
      return () => o.disconnect();
    }
  }, [ref]);
  return size;
}

function TextOverlayLayer({ 
  naturalSize, 
  texts, 
  regions, 
  globalStyle,
  styleOverrides,
  textScaleByTextId = {},
  pageId,
  renderBoundsByPage,
  onRenderBoundsChange,
}: { 
  naturalSize: { width: number; height: number }; 
  texts: PageText[]; 
  regions: WorkspaceMaskController["allRegions"]; 
  globalStyle: TypographyStyle;
  styleOverrides: Record<string, TypographyStyle>;
  textScaleByTextId?: Record<string, number>;
  pageId?: string;
  renderBoundsByPage?: Record<string, Record<string, [number, number, number, number]>>;
  onRenderBoundsChange?: (textId: string, bounds: [number, number, number, number]) => void;
}) {
  const { setRenderBounds } = useEditorStore();
  const regionById = useMemo(() => new Map(regions.map(r => [r.id, r])), [regions]);
  const appliedAutoGrowRef = useRef<Record<string, string>>({});
  
  const layoutInfoByTextId = useMemo(() => {
    const info = new Map<string, { bbox: number[] }>();
    const groups = new Map<string, typeof texts>();
    
    for (const text of texts) {
      const region = regionById.get(text.region_id);
      const parentId = region?.parent_region_id;
      if (parentId) {
        if (!groups.has(parentId)) groups.set(parentId, []);
        groups.get(parentId)!.push(text);
      }
    }

    for (const [balloonId, group] of groups.entries()) {
      const balloon = regionById.get(balloonId);
      const bbox = getRegionBbox(balloon);
      if (!balloon || !bbox || group.length <= 1) continue;
      
      let needsSlotFallback = false;
      for (let i = 0; i < group.length; i++) {
        const rA = getRegionBbox(regionById.get(group[i].region_id));
        if (!rA) { needsSlotFallback = true; break; }
        for (let j = i + 1; j < group.length; j++) {
          const rB = getRegionBbox(regionById.get(group[j].region_id));
          if (!rB || bboxIoU(rA, rB) > 0.35) {
            needsSlotFallback = true;
            break;
          }
        }
        if (needsSlotFallback) break;
      }

      if (!needsSlotFallback) {
        // Old behavior: use individual bounding boxes (blue boxes) for multi-text balloons
        group.forEach(text => {
          const r = getRegionBbox(regionById.get(text.region_id));
          if (r) info.set(text.id, { bbox: r });
        });
        continue;
      }

      // Ellipse vertical slotting fallback
      const sorted = [...group].sort((a, b) => {
        const rA = regionById.get(a.region_id);
        const rB = regionById.get(b.region_id);
        const oA = rA?.reading_order ?? 9999;
        const oB = rB?.reading_order ?? 9999;
        if (oA !== oB) return oA - oB;
        const boxA = getRegionBbox(rA);
        const boxB = getRegionBbox(rB);
        const yA = boxA ? (boxA[1] + boxA[3])/2 : 0;
        const yB = boxB ? (boxB[1] + boxB[3])/2 : 0;
        return yA - yB;
      });

      const [bx1, by1, bx2, by2] = bbox;
      const balloonW = Math.max(1, bx2 - bx1);
      const balloonH = Math.max(1, by2 - by1);
      const horizontalPad = Math.max(4, Math.round(balloonW * 0.06));
      const verticalPad = Math.max(4, Math.round(balloonH * 0.04));
      const slotH = balloonH / sorted.length;
      
      sorted.forEach((text, index) => {
        const sy1 = by1 + (index * slotH) + verticalPad;
        const sy2 = by1 + ((index + 1) * slotH) - verticalPad;
        
        const slotCy = (sy1 + sy2) / 2;
        const balloonCy = by1 + balloonH / 2;
        const yDistRatio = Math.min(0.95, Math.abs(slotCy - balloonCy) / (balloonH / 2));
        const ellipseWidthRatio = Math.sqrt(1 - yDistRatio * yDistRatio);
        const curveInset = (balloonW * (1 - ellipseWidthRatio)) / 2;
        
        const finalPadX = horizontalPad + curveInset;

        info.set(text.id, { 
          bbox: [bx1 + finalPadX, sy1, bx2 - finalPadX, Math.max(sy1 + 8, sy2)] 
        });
      });
    }
    return info;
  }, [texts, regionById]);

  const { renderedTexts, autoGrowCandidates } = useMemo(() => {
    const autoGrowCandidates: Array<{ textId: string; bounds: [number, number, number, number] }> = [];

    const renderedTexts = texts.map((text) => {
    const content = resolveTranslatedText(text).trim();
    const region = regionById.get(text.region_id);
    if (!region || !content) return null;

    let balloon = null;
    if (region.parent_region_id) {
      const parent = regionById.get(region.parent_region_id);
      if (parent?.region_kind === "balloon") balloon = parent;
    }
    
    const layoutInfo = layoutInfoByTextId.get(text.id);
    let w, h, boxCenterX, originalCenterY;
    let polygonAwareBalloon: PageRegion | null = null;
    
    const liveBounds = pageId && renderBoundsByPage ? renderBoundsByPage[pageId]?.[text.id] : null;
    const finalBounds = liveBounds || text.render_bounds;
    
    if (finalBounds) {
      const [rx, ry, rw, rh] = finalBounds;
      w = rw;
      h = rh;
      boxCenterX = rx + rw / 2;
      originalCenterY = ry + rh / 2;
    } else if (layoutInfo && layoutInfo.bbox) {
      const [lx1, ly1, lx2, ly2] = layoutInfo.bbox;
      w = Math.max(lx2 - lx1, 10);
      h = Math.max(ly2 - ly1, 10);
      boxCenterX = (lx1 + lx2) / 2;
      originalCenterY = (ly1 + ly2) / 2;
    } else {
      const targetRegion = balloon || region;
      const bbox = getRegionBbox(targetRegion);
      if (!bbox) return null;
      polygonAwareBalloon = balloon;
      
      const textRegionBbox = getRegionBbox(region);
      originalCenterY = textRegionBbox ? (textRegionBbox[1] + textRegionBbox[3]) / 2 : (bbox[1] + bbox[3]) / 2;
      const [x1, y1, x2, y2] = bbox;
      h = Math.max(y2 - y1, 10);
      
      const polySpan = getPolygonHorizontalWidthAtY(targetRegion.polygon_json, originalCenterY);
      w = polySpan ? Math.max(10, polySpan[1] - polySpan[0]) : Math.max(x2 - x1, 10);
      boxCenterX = polySpan ? (polySpan[0] + polySpan[1]) / 2 : (x1 + x2) / 2;
    }

    const style = styleOverrides[text.region_id] || globalStyle;
    const fontFamily = text.render_font_family || style.fontFamily || "Arial, sans-serif";
    const fillColor = text.render_color || style.color;
    const fontWeight = text.render_font_weight || style.fontWeight || "normal";
    const sizeMult = style.fontSize === "lg" ? 1.4 : style.fontSize === "sm" ? 0.8 : 1.0;
    const scale = text.render_scale ?? textScaleByTextId[text.id] ?? 1;

    const MIN_FONT_SIZE = 8;
    let fontSize = Math.floor(Math.min((w * 0.9) / 3.5, (h * 0.9) / 1.2) * sizeMult);
    if (fontSize < MIN_FONT_SIZE) fontSize = MIN_FONT_SIZE;
    
    let lh = fontSize * 1.2 * scale;
    let wrapW = Math.max(20, w * 0.9);
    
    let lines: { text: string; width: number }[] = [];
    let totalH = 0;
    for (let step = 0; step < 30 && fontSize >= MIN_FONT_SIZE; step++) {
      lh = fontSize * 1.2 * scale;
      const layout = layoutWithLines(
        prepareWithSegments(content, `${fontSize}px ${fontFamily}`, { whiteSpace: "pre-wrap" }),
        wrapW,
        fontSize * 1.2
      );
      lines = layout.lines;
      totalH = lines.length * lh;

      let polygonFits = true;
      let narrowestLineWidth = wrapW;
      if (polygonAwareBalloon?.polygon_json) {
        const firstLineY = originalCenterY - totalH / 2 + lh / 2;
        for (let i = 0; i < lines.length; i += 1) {
          const lineY = firstLineY + i * lh;
          const span = getPolygonHorizontalWidthAtY(polygonAwareBalloon.polygon_json, lineY);
          if (!span) continue;
          const allowedWidth = Math.max(20, (span[1] - span[0]) * 0.9);
          narrowestLineWidth = Math.min(narrowestLineWidth, allowedWidth);
          if ((lines[i]?.width ?? 0) > allowedWidth) {
            polygonFits = false;
          }
        }
      }

      if (!polygonFits && narrowestLineWidth < wrapW - 0.5) {
        wrapW = narrowestLineWidth;
        continue;
      }

      if (totalH <= h * 0.9 && polygonFits) break;
      fontSize -= 1;
    }

    // If minimum readable font still does not fit, auto-grow render bounds and keep center aligned.
    const targetHeight = Math.max(h, Math.ceil((totalH / 0.9) + 4));
    if (targetHeight > h + 1) {
      const centerY = originalCenterY;
      let nextY = centerY - targetHeight / 2;
      nextY = clamp(nextY, 0, Math.max(0, naturalSize.height - targetHeight));
      const nextX = clamp(boxCenterX - w / 2, 0, Math.max(0, naturalSize.width - w));
      const grown: [number, number, number, number] = [nextX, nextY, w, targetHeight];
      autoGrowCandidates.push({ textId: text.id, bounds: grown });
      h = targetHeight;
      originalCenterY = nextY + targetHeight / 2;
    }
    
    const textAnchor = style.textAlign === "left" ? "start" : style.textAlign === "right" ? "end" : "middle";
    const firstLineY = originalCenterY - totalH / 2 + lh / 2;
    const fallbackX = textAnchor === "middle" ? boxCenterX : textAnchor === "start" ? boxCenterX - (w / 2) + 4 : boxCenterX + (w / 2) - 4;
    const lineItems = lines.map((line, index) => {
      const lineY = firstLineY + index * lh;
      const span = polygonAwareBalloon?.polygon_json
        ? getPolygonHorizontalWidthAtY(polygonAwareBalloon.polygon_json, lineY)
        : null;
      const x = span
        ? textAnchor === "middle"
          ? (span[0] + span[1]) / 2
          : textAnchor === "start"
            ? span[0] + 4
            : span[1] - 4
        : fallbackX;

      return { ...line, x, y: lineY };
    });

    return (
      <g key={text.id}>
        <text 
          textAnchor={textAnchor} 
          dominantBaseline="middle" 
          fill={fillColor} 
          fontSize={fontSize * scale} 
          className="pointer-events-none select-none"
          style={{ 
            fontFamily, 
            fontWeight: fontWeight === "bold" ? "800" : "400" 
          }}
        >
          {lineItems.map((line, i) => <tspan key={i} x={line.x} y={line.y}>{line.text}</tspan>)}
        </text>
      </g>
    );
    });

    return { renderedTexts, autoGrowCandidates };
  }, [
    globalStyle,
    layoutInfoByTextId,
    naturalSize.height,
    naturalSize.width,
    pageId,
    regionById,
    renderBoundsByPage,
    styleOverrides,
    textScaleByTextId,
    texts,
  ]);

  useEffect(() => {
    if (!pageId || autoGrowCandidates.length === 0) return;
    for (const candidate of autoGrowCandidates) {
      const key = `${candidate.bounds.map((v) => Math.round(v * 10) / 10).join(",")}`;
      const prevKey = appliedAutoGrowRef.current[candidate.textId];
      if (prevKey === key) continue;
      const current = renderBoundsByPage?.[pageId]?.[candidate.textId];
      const materiallyDifferent =
        !current ||
        current.some((value, idx) => Math.abs(value - candidate.bounds[idx]) > 0.5);
      if (!materiallyDifferent) continue;

      appliedAutoGrowRef.current[candidate.textId] = key;
      setRenderBounds(pageId, candidate.textId, candidate.bounds);
      onRenderBoundsChange?.(candidate.textId, candidate.bounds);
    }
  }, [autoGrowCandidates, onRenderBoundsChange, pageId, renderBoundsByPage, setRenderBounds]);

  if (!naturalSize || !texts.length) return null;

  return (
    <svg className="pointer-events-none absolute inset-0 z-20 h-full w-full" viewBox={`0 0 ${naturalSize.width} ${naturalSize.height}`} preserveAspectRatio="none">
      {renderedTexts}
    </svg>
  );
}

function DraggableTextItem({
  text,
  pageId,
  activeTool,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  regionById
}: {
  text: PageText;
  pageId?: string;
  activeTool: string;
  onPointerDown: (e: React.PointerEvent, text: PageText, type: "drag" | "resize") => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  regionById: Map<string, PageRegion>;
}) {
  const storeBounds = useEditorStore(s => pageId ? s.renderBoundsByPage[pageId]?.[text.id] : null);
  const bounds = storeBounds || text.render_bounds;
  
  if (!bounds && activeTool !== "select") return null;

  let displayBounds = bounds;
  if (!displayBounds) {
    const region = regionById.get(text.region_id);
    const bbox = getRegionBbox(region);
    if (bbox) displayBounds = [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]];
  }

  if (!displayBounds) return null;

  const isActive = activeTool === "select";
  const INTERACTION_PAD = 12;

  return (
    <div
      className={cn(
        "absolute border-2 border-transparent transition-colors translated-text-draggable",
        isActive && "pointer-events-auto border-brand-gold/30 hover:border-brand-gold/60 cursor-move"
      )}
      style={{
        left: displayBounds[0] - INTERACTION_PAD,
        top: displayBounds[1] - INTERACTION_PAD,
        width: displayBounds[2] + INTERACTION_PAD * 2,
        height: displayBounds[3] + INTERACTION_PAD * 2,
      }}
      onPointerDown={(e) => { e.stopPropagation(); onPointerDown(e, text, "drag"); }}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {isActive && (
        <div 
          className="absolute bottom-0 right-0 h-5 w-5 cursor-nwse-resize bg-brand-gold/40 hover:bg-brand-gold/80 translated-text-draggable"
          onPointerDown={(e) => { e.stopPropagation(); onPointerDown(e, text, "resize"); }}
        />
      )}
    </div>
  );
}

function TextInteractionLayer({
  naturalSize,
  fittedSize,
  texts,
  regions,
  activeTool,
  onRenderBoundsChange,
  pageId,
  onSelectRegion,
}: {
  naturalSize: { width: number; height: number };
  fittedSize: { width: number; height: number } | null;
  texts: PageText[];
  regions: PageRegion[];
  activeTool: string;
  onRenderBoundsChange?: (textId: string, bounds: [number, number, number, number]) => void;
  pageId?: string;
  onSelectRegion?: (regionId: string) => void;
}) {
  const { setRenderBounds } = useEditorStore();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [resizingId, setResizingId] = useState<string | null>(null);
  const startRef = useRef({ x: 0, y: 0, bx: 0, by: 0, bw: 0, bh: 0 });
  const didMutateRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const regionById = useMemo(() => new Map(regions.map(r => [r.id, r])), [regions]);

  const fitScale = fittedSize ? fittedSize.width / naturalSize.width : 1;

  const resolvePoint = (clientX: number, clientY: number): [number, number] | null => {
    if (!containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const x = ((clientX - rect.left) / rect.width) * naturalSize.width;
    const y = ((clientY - rect.top) / rect.height) * naturalSize.height;
    return [x, y];
  };

  const resolveInitialBounds = useCallback((text: PageText): [number, number, number, number] | null => {
    if (text.render_bounds) return text.render_bounds;
    const region = regionById.get(text.region_id);
    if (!region) return null;

    // Default to balloon-aware bounds so interaction starts from the same visual model as rendering.
    if (region.parent_region_id) {
      const balloon = regionById.get(region.parent_region_id);
      if (balloon?.region_kind === "balloon") {
        const balloonBox = getRegionBbox(balloon);
        if (balloonBox) {
          const textBox = getRegionBbox(region);
          const centerY = textBox
            ? (textBox[1] + textBox[3]) / 2
            : (balloonBox[1] + balloonBox[3]) / 2;
          const span = getPolygonHorizontalWidthAtY(balloon.polygon_json, centerY);
          const width = Math.max(10, span ? (span[1] - span[0]) : (balloonBox[2] - balloonBox[0]));
          const height = Math.max(10, balloonBox[3] - balloonBox[1]);
          const centerX = span
            ? (span[0] + span[1]) / 2
            : (balloonBox[0] + balloonBox[2]) / 2;
          return [centerX - width / 2, centerY - height / 2, width, height];
        }
      }
    }

    const fallback = getRegionBbox(region);
    if (!fallback) return null;
    return [fallback[0], fallback[1], fallback[2] - fallback[0], fallback[3] - fallback[1]];
  }, [regionById]);

  const handlePointerDown = (e: React.PointerEvent, text: PageText, type: "drag" | "resize") => {
    if (activeTool !== "select") return;
    e.stopPropagation();
    onSelectRegion?.(text.region_id);
    
    const point = resolvePoint(e.clientX, e.clientY);
    if (!point) return;

    const currentBounds = resolveInitialBounds(text);
    
    if (!currentBounds) return;
    didMutateRef.current = false;

    if (type === "drag") setDraggingId(text.id);
    else setResizingId(text.id);

    startRef.current = {
      x: point[0],
      y: point[1],
      bx: currentBounds[0],
      by: currentBounds[1],
      bw: currentBounds[2],
      bh: currentBounds[3]
    };
    
    (e.target as Element).setPointerCapture(e.pointerId);
  };

  const handleBubbleHitAreaPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (activeTool !== "select") return;
    const target = e.target as Element;
    if (target.closest(".translated-text-draggable")) return;

    const point = resolvePoint(e.clientX, e.clientY);
    if (!point) return;

    const withBubble = texts
      .map((text) => {
        const region = regionById.get(text.region_id);
        if (!region?.parent_region_id) return null;
        const bubble = regionById.get(region.parent_region_id);
        if (!bubble || bubble.region_kind !== "balloon") return null;

        const content = resolveTranslatedText(text).trim();
        if (!content) return null;

        const bounds = resolveInitialBounds(text);
        if (!bounds) return null;

        if (!pointInPolygon(point, bubble.polygon_json)) return null;
        const centerX = bounds[0] + bounds[2] / 2;
        const centerY = bounds[1] + bounds[3] / 2;
        const dist = Math.hypot(point[0] - centerX, point[1] - centerY);
        return { text, bounds, dist };
      })
      .filter((item): item is { text: PageText; bounds: [number, number, number, number]; dist: number } => Boolean(item))
      .sort((a, b) => a.dist - b.dist);

    const best = withBubble[0];
    if (!best) return;

    e.stopPropagation();
    onSelectRegion?.(best.text.region_id);
    startRef.current = {
      x: point[0],
      y: point[1],
      bx: best.bounds[0],
      by: best.bounds[1],
      bw: best.bounds[2],
      bh: best.bounds[3],
    };
    setDraggingId(best.text.id);
    didMutateRef.current = false;
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    const id = draggingId || resizingId;
    if (!id) return;

    const point = resolvePoint(e.clientX, e.clientY);
    if (!point) return;

    const dx = point[0] - startRef.current.x;
    const dy = point[1] - startRef.current.y;

    const movedEnough = Math.hypot(dx, dy) >= 1.5;
    let nextBounds: [number, number, number, number];
    if (draggingId) {
      if (!movedEnough) return;
      nextBounds = [
        startRef.current.bx + dx,
        startRef.current.by + dy,
        startRef.current.bw,
        startRef.current.bh
      ];
    } else {
      if (!movedEnough) return;
      nextBounds = [
        startRef.current.bx,
        startRef.current.by,
        Math.max(20, startRef.current.bw + dx),
        Math.max(20, startRef.current.bh + dy)
      ];
    }

    if (pageId) {
      didMutateRef.current = true;
      setRenderBounds(pageId, id, nextBounds);
    }
  };

  const handlePointerUp = () => {
    const id = draggingId || resizingId;
    if (id && didMutateRef.current && onRenderBoundsChange && pageId) {
      const bounds = useEditorStore.getState().renderBoundsByPage[pageId]?.[id];
      if (bounds) onRenderBoundsChange(id, bounds);
    }
    didMutateRef.current = false;
    setDraggingId(null);
    setResizingId(null);
  };

  return (
    <div 
      ref={containerRef}
      className="absolute top-0 left-0 z-30 pointer-events-none"
      style={{ 
        width: naturalSize.width, 
        height: naturalSize.height,
        transform: `scale(${fitScale})`,
        transformOrigin: "top left"
      }}
      onPointerDown={handleBubbleHitAreaPointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      {texts.map((text) => (
        <DraggableTextItem
          key={text.id}
          text={text}
          pageId={pageId}
          activeTool={activeTool}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          regionById={regionById}
        />
      ))}
    </div>
  );
}

function WorkspaceToolRail({
  controller,
  eraserMode,
  onEraserModeChange,
  eraseBrushSize,
  onEraseBrushSizeChange,
  onClearEraseLayer,
  canUsePixelErase,
  hasUnsavedEraseChanges,
  hasSavedEraseDraft,
  isSavingEraseChanges,
  onSaveEraseDraft,
  onConfirmEraseDraft,
}: {
  controller: WorkspaceMaskController;
  eraserMode: "mask_delete" | "pixel_erase";
  onEraserModeChange: (mode: "mask_delete" | "pixel_erase") => void;
  eraseBrushSize: number;
  onEraseBrushSizeChange: (value: number) => void;
  onClearEraseLayer: () => void;
  canUsePixelErase: boolean;
  hasUnsavedEraseChanges: boolean;
  hasSavedEraseDraft: boolean;
  isSavingEraseChanges: boolean;
  onSaveEraseDraft: () => void;
  onConfirmEraseDraft: () => void;
}) {
  const zoom = useTransformComponent(c => Math.round(c.state.scale * 100));
  const { zoomIn, zoomOut } = useControls();
  return (
    <FloatingToolRail 
      zoomLevel={zoom} 
      onZoomOut={() => zoomOut(0.2, 300)} 
      onZoomIn={() => zoomIn(0.2, 300)} 
      activeTool={controller.activeTool} 
      onToolChange={controller.setActiveTool}
      maskController={controller}
      eraserMode={eraserMode}
      onEraserModeChange={onEraserModeChange}
      eraseBrushSize={eraseBrushSize}
      onEraseBrushSizeChange={onEraseBrushSizeChange}
      onClearEraseLayer={onClearEraseLayer}
      canUsePixelErase={canUsePixelErase}
      hasUnsavedEraseChanges={hasUnsavedEraseChanges}
      hasSavedEraseDraft={hasSavedEraseDraft}
      isSavingEraseChanges={isSavingEraseChanges}
      onSaveEraseDraft={onSaveEraseDraft}
      onConfirmEraseDraft={onConfirmEraseDraft}
    />
  );
}

function kindBadgeClass(kind: string, active: boolean): string {
  if (!active) {
    return "h-[31px] rounded-[6px] border border-[#D8C9B8] bg-[#FBF7F1] px-[10px] text-[11px] font-semibold text-[#5C4D42] transition-colors hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
  }
  if (kind === "text") {
    return "h-[31px] rounded-[6px] border border-[#38BDF8] bg-[#E0F2FE] px-[10px] text-[11px] font-semibold text-[#075985] shadow-[0_4px_10px_rgba(56,189,248,0.22)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
  }
  if (kind === "panel") {
    return "h-[31px] rounded-[6px] border border-[#34D399] bg-[#D1FAE5] px-[10px] text-[11px] font-semibold text-[#065F46] shadow-[0_4px_10px_rgba(52,211,153,0.22)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
  }
  if (kind === "balloon") {
    return "h-[31px] rounded-[6px] border border-[#FACC15] bg-[#FEF9C3] px-[10px] text-[11px] font-semibold text-[#854D0E] shadow-[0_4px_10px_rgba(250,204,21,0.22)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
  }
  return "h-[31px] rounded-[6px] border border-brand-border-yellowStrong bg-[#FFF1D4] px-[10px] text-[11px] font-semibold text-[#5C4D42] shadow-[0_4px_10px_rgba(217,174,47,0.18)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
}

export default function Workspace({
  imageUrl, isInpaintedView = false, pageId, maskController, selectedTextRegionId, onTextRegionSelect, readingOrderLabelsByRegionId, texts = [], showTranslatedText, textScaleByTextId, onTextRegionManualPlacement, onRenderBoundsChange, onInpaintedImageSaved
}: WorkspaceProps) {
  const { displayedUrl, isLoading, hasError } = useImagePreload(imageUrl);
  const renderBoundsByPage = useEditorStore(s => s.renderBoundsByPage);

  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const [eraserMode, setEraserMode] = useState<"mask_delete" | "pixel_erase">("mask_delete");
  const [eraseBrushSize, setEraseBrushSize] = useState(28);
  const [hasUnsavedEraseChanges, setHasUnsavedEraseChanges] = useState(false);
  const [savedEraseDraftDataUrl, setSavedEraseDraftDataUrl] = useState<string | null>(null);
  const [isSavingEraseChanges, setIsSavingEraseChanges] = useState(false);
  const [isInpaintCanvasReady, setIsInpaintCanvasReady] = useState(false);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const inpaintCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const eraseDragRef = useRef<[number, number] | null>(null);
  const viewportSize = useViewportSize(viewportRef);

  const displayedIsInpaintedView = isInpaintedView && displayedUrl === imageUrl;
  const canUsePixelErase = displayedIsInpaintedView && isInpaintCanvasReady;
  const pixelEraseActive = canUsePixelErase && maskController.activeTool === "eraser" && eraserMode === "pixel_erase";
  const overlayRegions = useMemo(
    () =>
      maskController.regions
        .map((r) => {
          const isText = r.region_kind === "text";
          const editedPolygon = maskController.editablePolygonsByRegionId[r.id];
          const boxPolygon = bboxToPolygon(getRegionBbox(r));
          return {
            id: r.id,
            regionKind: r.region_kind,
            displayPolygon:
              isText &&
              (r.confidence ?? 0) >= 1.0 &&
              Array.isArray(r.polygon_json) &&
              r.polygon_json.length >= 3
                ? r.polygon_json
                : isText
                  ? boxPolygon
                  : r.polygon_json?.length
                    ? r.polygon_json
                    : boxPolygon,
            editablePolygon:
              editedPolygon ?? (isText ? boxPolygon : (r.polygon_json ?? boxPolygon)),
            readingOrderLabel: isText ? readingOrderLabelsByRegionId?.[r.id] : undefined,
          };
        })
        .filter((r): r is Exclude<typeof r, null> => r !== null)
        .filter((r) => r.displayPolygon.length > 2),
    [maskController, readingOrderLabelsByRegionId],
  );

  const clearEraseLayer = useCallback(() => {
    setHasUnsavedEraseChanges(false);
    setSavedEraseDraftDataUrl(null);
    setIsInpaintCanvasReady(false);
    if (!inpaintCanvasRef.current || !naturalSize || !displayedUrl || !displayedIsInpaintedView) return;
    const canvas = inpaintCanvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      canvas.width = naturalSize.width;
      canvas.height = naturalSize.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      setIsInpaintCanvasReady(true);
    };
    image.onerror = () => setIsInpaintCanvasReady(false);
    image.src = displayedUrl;
  }, [displayedIsInpaintedView, displayedUrl, naturalSize]);

  const saveEraseDraft = useCallback(() => {
    const canvas = inpaintCanvasRef.current;
    if (!canvas || !hasUnsavedEraseChanges) return;
    const pngDataUrl = canvas.toDataURL("image/png");
    setSavedEraseDraftDataUrl(pngDataUrl);
    setHasUnsavedEraseChanges(false);
  }, [hasUnsavedEraseChanges]);

  const confirmEraseDraft = useCallback(async () => {
    if (!pageId || !savedEraseDraftDataUrl || isSavingEraseChanges) return;
    setIsSavingEraseChanges(true);
    try {
      await savePageInpaintCleanup(pageId, { image_data_url: savedEraseDraftDataUrl });
      setSavedEraseDraftDataUrl(null);
      await onInpaintedImageSaved?.();
    } finally {
      setIsSavingEraseChanges(false);
    }
  }, [isSavingEraseChanges, onInpaintedImageSaved, pageId, savedEraseDraftDataUrl]);

  useEffect(() => {
    eraseDragRef.current = null;
    clearEraseLayer();
  }, [clearEraseLayer]);

  useEffect(() => {
    if (maskController.activeTool !== "eraser") {
      eraseDragRef.current = null;
    }
  }, [maskController.activeTool]);

  useEffect(() => {
    if (canUsePixelErase) return;
    eraseDragRef.current = null;
    if (eraserMode !== "mask_delete") {
      setEraserMode("mask_delete");
    }
    clearEraseLayer();
  }, [canUsePixelErase, clearEraseLayer, eraserMode]);

  const drawEraseSegment = useCallback((from: [number, number], to: [number, number]) => {
    const canvas = inpaintCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.save();
    ctx.strokeStyle = "#ffffff";
    ctx.fillStyle = "#ffffff";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(1, eraseBrushSize);
    ctx.beginPath();
    ctx.moveTo(from[0], from[1]);
    ctx.lineTo(to[0], to[1]);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(to[0], to[1], Math.max(2, eraseBrushSize / 2), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }, [eraseBrushSize]);

  const onErasePointerDown = useCallback((event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!pixelEraseActive || !naturalSize) return;
    const point = toCanvasPoint(event, naturalSize);
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    eraseDragRef.current = point;
    drawEraseSegment(point, point);
    setHasUnsavedEraseChanges(true);
    setSavedEraseDraftDataUrl(null);
  }, [drawEraseSegment, naturalSize, pixelEraseActive]);

  const onErasePointerMove = useCallback((event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!pixelEraseActive || !naturalSize || !eraseDragRef.current) return;
    const point = toCanvasPoint(event, naturalSize);
    drawEraseSegment(eraseDragRef.current, point);
    eraseDragRef.current = point;
    setHasUnsavedEraseChanges(true);
    setSavedEraseDraftDataUrl(null);
  }, [drawEraseSegment, naturalSize, pixelEraseActive]);

  const stopEraseDrag = useCallback(() => {
    eraseDragRef.current = null;
  }, []);

  const interactions = useMaskOverlayInteractions({
    mode: 
      maskController.activeTool === "select" ? "select" : 
      maskController.activeTool === "eraser" && eraserMode === "mask_delete" ? "erase" : 
      maskController.activeTool === "pen" ? "pen" : "none",
    penShape: maskController.penShape ?? undefined,
    naturalSize: naturalSize ?? { width: 1000, height: 1000 },
    regions: overlayRegions,
    onRegionPolygonChange: (id, p) => { maskController.onRegionPolygonChange(id, p); if (maskController.regions.find(r => r.id === id)?.region_kind === "text") onTextRegionManualPlacement?.(id); },
    onRegionSelect: (id) => { maskController.setActiveMaskId(id); if (maskController.regions.find(r => r.id === id)?.region_kind === "text") onTextRegionSelect?.(id); },
    onRegionDelete: maskController.onRegionDelete,
    onRegionCreate: (p) => maskController.onRegionCreate(maskController.penTarget, p),
  });
  const fittedSize = useMemo(() => {
    if (!naturalSize || !viewportSize) return null;
    const s = Math.min(Math.max(viewportSize.width, 1) / naturalSize.width, Math.max(viewportSize.height, 1) / naturalSize.height);
    return { width: Math.max(naturalSize.width * s, 1), height: Math.max(naturalSize.height * s, 1) };
  }, [naturalSize, viewportSize]);

  if (!displayedUrl || hasError) return (
    <div className="flex min-h-0 min-w-0 flex-1 items-center bg-brand-surface-muted px-6 pb-2.5 pt-3.5">
      <div className="flex flex-1 items-center justify-center rounded-xl border border-brand-border-pink bg-brand-surface-alt p-3"><span className="font-bold text-brand-text-workflow">{hasError ? "Failed to load" : "No image"}</span></div>
    </div>
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 items-center overflow-hidden bg-brand-surface-muted px-6 pb-2.5 pt-3.5">
      <TransformWrapper initialScale={1} minScale={0.1} maxScale={20} limitToBounds={false} panning={{ disabled: maskController.activeTool !== "select", wheelPanning: maskController.activeTool === "select", allowLeftClickPan: true, excluded: ["mask-overlay-handle", "mask-overlay-control", "translated-text-draggable"] }} wheel={{ wheelDisabled: true, smoothStep: 0.05 }} pinch={{ step: 15 }} doubleClick={{ disabled: false }}>
        <div data-tool-rail-boundary="true" className="flex h-full min-w-0 w-full overflow-hidden gap-5">
          <div className="flex h-full min-w-0 flex-1 flex-col gap-3 rounded-xl border border-brand-border-pink bg-brand-surface-alt p-3 shadow-md">
            {maskController.allRegions.length > 0 && (
              <div className="flex w-full items-center justify-between gap-3">
                <div className="flex gap-2">
                  <button data-no-pan onClick={maskController.toggleShowMasks} className={cn("h-[31px] rounded-[6px] border border-[#D8C9B8] bg-[#FBF7F1] px-[10px] text-[11px] font-semibold text-[#5C4D42] transition-colors hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold")}>
                    {maskController.showMasks ? "Hide masks" : "Show masks"} ({overlayRegions.length}/{maskController.allRegions.length})
                  </button>
                  <button data-no-pan onClick={maskController.toggleShowLabels} className={cn("h-[31px] rounded-[6px] border border-[#D8C9B8] bg-[#FBF7F1] px-[10px] text-[11px] font-semibold text-[#5C4D42] transition-colors hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold")}>
                    {maskController.showLabels ? "Hide tags" : "Show tags"}
                  </button>
                  <div className="flex flex-wrap items-center gap-1">
                    <button
                      data-no-pan
                      type="button"
                      onClick={maskController.setFilterAll}
                      className={kindBadgeClass("all", maskController.filter.mode !== "kind")}
                    >
                      All
                    </button>
                    {maskController.availableRegionKinds.map((kind) => (
                      <button
                        key={kind}
                      type="button"
                      onClick={() => maskController.setFilterByKind(kind)}
                        className={kindBadgeClass(
                          kind,
                          maskController.filter.mode === "kind" && maskController.filter.regionKind === kind,
                        )}
                      >
                        {kind}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex h-[31px] items-center rounded-[4px] border border-[#D8C9B8] bg-[#F1E7DA] px-[10px]"><span className="text-[10px] font-bold text-[#FF5C00]">Mask Review</span></div>
              </div>
            )}
            <div ref={viewportRef} className={`relative flex-1 overflow-hidden rounded-lg border border-brand-border-pinkLight bg-white p-[14px] ${maskController.activeTool === "select" ? "cursor-grab active:cursor-grabbing" : "cursor-default"}`}>
              <TransformComponent wrapperClass="!w-full !h-full">
                <div
                  data-export-target="workspace-canvas"
                  className={fittedSize ? "relative shrink-0" : "relative inline-block"}
                  style={fittedSize || undefined}
                >
                  <img
                    src={displayedUrl}
                    alt="Page"
                    className={cn(
                      "pointer-events-none block",
                      fittedSize ? "h-full w-full" : "h-auto max-h-full max-w-full w-auto object-contain",
                    )}
                    onLoad={e => setNaturalSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })}
                  />
                  {displayedIsInpaintedView ? (
                    <canvas
                      ref={inpaintCanvasRef}
                      className={cn(
                        "absolute inset-0 z-[5] h-full w-full transition-opacity duration-75",
                        isInpaintCanvasReady ? "opacity-100" : "opacity-0",
                        pixelEraseActive && isInpaintCanvasReady ? "pointer-events-auto cursor-crosshair" : "pointer-events-none",
                      )}
                      width={naturalSize?.width ?? 0}
                      height={naturalSize?.height ?? 0}
                      onPointerDown={onErasePointerDown}
                      onPointerMove={onErasePointerMove}
                      onPointerUp={stopEraseDrag}
                      onPointerCancel={stopEraseDrag}
                      aria-label="Editable inpainted image"
                    />
                  ) : null}
                  <div data-export-hide="true">
                    <MaskOverlay
                      regions={overlayRegions}
                      naturalSize={naturalSize}
                      visible={showTranslatedText ? false : maskController.showMasks}
                      showLabels={maskController.showLabels}
                      interactive
                      showHandles={maskController.activeTool === "select"}
                      eraseMode={maskController.activeTool === "eraser" && eraserMode === "mask_delete"}
                      activeMaskId={selectedTextRegionId ?? maskController.activeMaskId}
                      isDragging={interactions.isDragging}
                      drawingPoints={interactions.drawingPoints}
                      onOverlayPointerDown={interactions.onOverlayPointerDown}
                      onOverlayPointerMove={interactions.onOverlayPointerMove}
                      onOverlayPointerUp={interactions.onOverlayPointerUp}
                      onOverlayPointerCancel={interactions.onOverlayPointerCancel}
                      onHandlePointerDown={interactions.onHandlePointerDown}
                      onPolygonPointerDown={interactions.onPolygonPointerDown}
                    />
                  </div>
                  {showTranslatedText && naturalSize && (
                    <TextOverlayLayer 
                      naturalSize={naturalSize} 
                      texts={texts} 
                      regions={maskController.allRegions} 
                      globalStyle={maskController.globalTextStyle}
                      styleOverrides={maskController.textStylesByRegionId}
                      textScaleByTextId={textScaleByTextId}
                      pageId={pageId}
                      renderBoundsByPage={renderBoundsByPage}
                      onRenderBoundsChange={onRenderBoundsChange}
                    />
                  )}
                  {showTranslatedText && naturalSize && (
                    <TextInteractionLayer
                      naturalSize={naturalSize}
                      fittedSize={fittedSize}
                      texts={texts}
                      regions={maskController.allRegions}
                      activeTool={maskController.activeTool}
                      onRenderBoundsChange={onRenderBoundsChange}
                      pageId={pageId}
                      onSelectRegion={onTextRegionSelect}
                    />
                  )}
                </div>
              </TransformComponent>
              {isLoading && <div className="absolute left-4 top-4 rounded-full border border-brand-border-gold bg-white px-3 py-1 text-[11px] font-semibold">Loading page...</div>}
              {!isLoading && maskController.maskError && <div className="absolute left-4 top-14 max-w-[380px] rounded-lg border border-red-200 bg-white/95 px-3 py-2 text-[11px] font-semibold text-red-700 shadow-sm">{maskController.maskError}</div>}
            </div>
          </div>
          <aside className="relative z-30 flex w-[72px] shrink-0 flex-col justify-center">
            <WorkspaceToolRail
              controller={maskController}
              eraserMode={eraserMode}
              onEraserModeChange={(mode) => {
                if (!canUsePixelErase && mode === "pixel_erase") {
                  setEraserMode("mask_delete");
                  stopEraseDrag();
                  clearEraseLayer();
                  return;
                }
                setEraserMode(mode);
                if (mode !== "pixel_erase") stopEraseDrag();
              }}
              canUsePixelErase={canUsePixelErase}
              eraseBrushSize={eraseBrushSize}
              onEraseBrushSizeChange={setEraseBrushSize}
              onClearEraseLayer={() => {
                stopEraseDrag();
                clearEraseLayer();
              }}
              hasUnsavedEraseChanges={hasUnsavedEraseChanges}
              hasSavedEraseDraft={Boolean(savedEraseDraftDataUrl)}
              isSavingEraseChanges={isSavingEraseChanges}
              onSaveEraseDraft={saveEraseDraft}
              onConfirmEraseDraft={confirmEraseDraft}
            />
          </aside>
        </div>
      </TransformWrapper>
    </div>
  );
}
