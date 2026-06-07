import { Eraser, MousePointer2, Pen } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "../../lib/utils";
import type { EditorTool, WorkspaceMaskController } from "../../hooks/editor/maskEditorTypes";

export type { EditorTool };

type FlyoutSide = "right" | "left";

const FLYOUT_WIDTH = 240;
const FLYOUT_GAP = 12;
const VIEWPORT_EDGE_GUTTER = 16;
const TOOL_RAIL_BOUNDARY_SELECTOR = "[data-tool-rail-boundary='true']";

interface FloatingToolRailProps {
  zoomLevel: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  activeTool: EditorTool;
  onToolChange: (tool: EditorTool) => void;
  maskController: WorkspaceMaskController;
  eraserMode?: "mask_delete" | "pixel_erase";
  onEraserModeChange?: (mode: "mask_delete" | "pixel_erase") => void;
  eraseBrushSize?: number;
  onEraseBrushSizeChange?: (value: number) => void;
  onClearEraseLayer?: () => void;
  canUsePixelErase?: boolean;
  hasUnsavedEraseChanges?: boolean;
  hasSavedEraseDraft?: boolean;
  isSavingEraseChanges?: boolean;
  onSaveEraseDraft?: () => void;
  onConfirmEraseDraft?: () => void;
  disabled?: boolean;
}

export default function FloatingToolRail({
  zoomLevel,
  onZoomIn,
  onZoomOut,
  activeTool,
  onToolChange,
  maskController,
  eraserMode = "mask_delete",
  onEraserModeChange,
  eraseBrushSize = 28,
  onEraseBrushSizeChange,
  onClearEraseLayer,
  canUsePixelErase = true,
  hasUnsavedEraseChanges = false,
  hasSavedEraseDraft = false,
  isSavingEraseChanges = false,
  onSaveEraseDraft,
  onConfirmEraseDraft,
  disabled = false,
}: FloatingToolRailProps) {
  const railRef = useRef<HTMLDivElement>(null);
  const [flyoutSide, setFlyoutSide] = useState<FlyoutSide>("right");
  const [isFlyoutOpen, setIsFlyoutOpen] = useState(true);
  const [isEraserFlyoutOpen, setIsEraserFlyoutOpen] = useState(true);

  const { penShape, setPenShape, penTarget, setPenTarget } = maskController;

  const isPenActive = activeTool === "pen";
  const isEraserActive = activeTool === "eraser";

  useEffect(() => {
    if (!isPenActive && !isEraserActive) {
      return;
    }

    if (isPenActive) setIsFlyoutOpen(true);
    if (isEraserActive) setIsEraserFlyoutOpen(true);

    const updateFlyoutSide = () => {
      const rail = railRef.current;
      if (!rail) return;

      const rect = rail.getBoundingClientRect();
      const boundary = rail.closest(TOOL_RAIL_BOUNDARY_SELECTOR) as HTMLElement | null;
      const boundaryRect = boundary?.getBoundingClientRect();
      const rightLimit = boundaryRect?.right ?? window.innerWidth;
      const leftLimit = boundaryRect?.left ?? 0;
      const canOpenRight = rect.right + FLYOUT_GAP + FLYOUT_WIDTH <= rightLimit - VIEWPORT_EDGE_GUTTER;
      const canOpenLeft = rect.left - FLYOUT_GAP - FLYOUT_WIDTH >= leftLimit + VIEWPORT_EDGE_GUTTER;
      setFlyoutSide(canOpenRight || !canOpenLeft ? "right" : "left");
    };

    updateFlyoutSide();
    window.addEventListener("resize", updateFlyoutSide);
    return () => window.removeEventListener("resize", updateFlyoutSide);
  }, [isEraserActive, isPenActive]);

  const toolButtonClass = (tool: string) =>
    cn(
      "flex h-[42px] w-[42px] items-center justify-center rounded-md border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold",
      activeTool === tool
        ? "border-[#FFB36A] bg-[#FFCF7A] text-[#17130D] shadow-[0_6px_14px_rgba(255,180,110,0.2)]"
        : "border-[#D8C9B8] bg-[#FBF7F1] text-[#453D35] hover:bg-white",
    );

  const chipClass = (active: boolean) =>
    cn(
      "h-[28px] rounded-full border px-3 text-[11px] font-semibold transition-all duration-300 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100 disabled:hover:shadow-none",
      active
        ? "border-[#FFB36A] bg-gradient-to-b from-[#FFCF7A] to-[#FFBF59] text-[#17130D] shadow-[0_4px_12px_rgba(255,180,110,0.3)] scale-105"
        : "border-[#E8DFD5] bg-white/50 text-[#6A5F53] hover:bg-white hover:shadow-sm hover:scale-[1.03]",
    );

  const targetChipClass = (target: "panel" | "balloon" | "text", active: boolean) => {
    if (!active) {
      return "h-[28px] rounded-full border border-[#E8DFD5] bg-white/50 px-3 text-[11px] font-semibold text-[#6A5F53] transition-all duration-300 ease-out hover:scale-[1.03] hover:bg-white hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold disabled:cursor-not-allowed disabled:opacity-40";
    }

    if (target === "text") {
      return "h-[28px] rounded-full border border-[#38BDF8] bg-[#E0F2FE] px-3 text-[11px] font-semibold text-[#075985] shadow-[0_4px_12px_rgba(56,189,248,0.28)] transition-all duration-300 ease-out scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
    }
    if (target === "panel") {
      return "h-[28px] rounded-full border border-[#34D399] bg-[#D1FAE5] px-3 text-[11px] font-semibold text-[#065F46] shadow-[0_4px_12px_rgba(52,211,153,0.25)] transition-all duration-300 ease-out scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
    }
    return "h-[28px] rounded-full border border-[#FACC15] bg-[#FEF9C3] px-3 text-[11px] font-semibold text-[#854D0E] shadow-[0_4px_12px_rgba(250,204,21,0.28)] transition-all duration-300 ease-out scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold";
  };

  const flyoutPositionClass = useMemo(
    () => (flyoutSide === "right" ? "left-[84px]" : "right-[84px]"),
    [flyoutSide],
  );

  return (
    <div className="relative w-[72px] overflow-visible">
      {/* Pipeline error banner */}
      {maskController.maskError && (
        <div className="mb-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700">
          {maskController.maskError}
        </div>
      )}

      <div
        ref={railRef}
        className={cn(
          "flex w-[72px] shrink-0 flex-col items-center justify-center gap-3 rounded-[12px] border border-[#F3E0D2] bg-white px-[10px] py-[12px] shadow-[0_10px_24px_rgba(0,0,0,0.06)]",
          disabled ? "pointer-events-none opacity-50" : "",
        )}
      >
        <div className="flex flex-col items-center gap-[9px]">
          <button
            className={toolButtonClass("select")}
            onClick={() => onToolChange("select")}
            aria-label="Select tool"
            aria-pressed={activeTool === "select"}
          >
            <MousePointer2 className="h-[20px] w-[20px] pointer-events-none" strokeWidth={1.75} />
          </button>
          <button
            className={toolButtonClass("eraser")}
            onClick={() => {
              if (activeTool === "eraser") {
                setIsEraserFlyoutOpen((prev) => !prev);
              } else {
                onToolChange("eraser");
              }
            }}
            aria-label="Eraser tool"
            aria-pressed={activeTool === "eraser"}
          >
            <Eraser className="h-[20px] w-[20px] pointer-events-none" strokeWidth={1.75} />
          </button>
          <button
            className={toolButtonClass("pen")}
            onClick={() => {
              if (activeTool === "pen") {
                setIsFlyoutOpen((prev) => !prev);
              } else {
                onToolChange("pen");
              }
            }}
            aria-label="Pen tool"
            aria-pressed={activeTool === "pen"}
          >
            <Pen className="h-[18px] w-[18px] pointer-events-none" strokeWidth={0} fill="currentColor" />
          </button>
        </div>

        <div className="h-px w-6 bg-[#DDD5CB]" aria-hidden="true" />

        <div className="flex w-[42px] flex-col items-center gap-[6px] rounded-[8px] border border-[#FFD1B5] bg-[#FFF3EA] px-[6px] py-2">
          <span
            className="font-caption text-[10px] font-bold leading-none text-[#666666]"
            aria-live="polite"
          >
            {zoomLevel}%
          </span>
          <div className="flex flex-col items-center gap-[6px]">
            <button
              onClick={onZoomOut}
              className="flex h-[30px] w-[30px] items-center justify-center rounded-[8px] border border-[#D8C9B8] bg-white text-[18px] leading-none text-[#3D362E] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
              aria-label="Zoom out"
            >
              −
            </button>
            <button
              onClick={onZoomIn}
              className="flex h-[30px] w-[30px] items-center justify-center rounded-[8px] border border-[#D8C9B8] bg-white text-[18px] leading-none text-[#3D362E] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
              aria-label="Zoom in"
            >
              +
            </button>
          </div>
        </div>
      </div>

      <div
        className={cn(
          "absolute top-[56px] z-20 w-[240px] rounded-[16px] border border-white/60 bg-white/80 px-4 py-3.5 shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15),0_0_0_1px_rgba(0,0,0,0.03)] backdrop-blur-2xl transition-all duration-300 ease-out origin-top",
          flyoutPositionClass,
          isEraserActive && isEraserFlyoutOpen
            ? "opacity-100 scale-100 translate-x-0 pointer-events-auto"
            : "opacity-0 scale-95 pointer-events-none",
          !(isEraserActive && isEraserFlyoutOpen) && flyoutSide === "left" && "translate-x-3",
          !(isEraserActive && isEraserFlyoutOpen) && flyoutSide === "right" && "-translate-x-3",
        )}
        role="group"
        aria-label="Eraser tool options"
        aria-hidden={!(isEraserActive && isEraserFlyoutOpen)}
      >
        <div className="mb-3 flex items-center justify-between border-b border-[#F0EAE5] pb-2.5">
          <p className="text-[13px] font-bold tracking-tight text-[#2F2923]">Eraser</p>
        </div>
        <div className="space-y-3">
          <section>
            <p className="mb-2 text-[11px] font-semibold text-[#4A4138]">Mode</p>
            <div className="flex flex-wrap items-center gap-[6px]">
              <button type="button" className={chipClass(eraserMode === "mask_delete")} onClick={() => onEraserModeChange?.("mask_delete")} aria-pressed={eraserMode === "mask_delete"}>
                Mask Delete
              </button>
              <button
                type="button"
                className={chipClass(eraserMode === "pixel_erase")}
                onClick={() => onEraserModeChange?.("pixel_erase")}
                aria-pressed={eraserMode === "pixel_erase"}
                disabled={!canUsePixelErase}
              >
                Normal Erase
              </button>
            </div>
          </section>
          <section className={cn("space-y-2", eraserMode !== "pixel_erase" && "opacity-50")}>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold text-[#4A4138]">Brush Size</p>
              <span className="text-[10px] font-semibold text-[#857C72]">{eraseBrushSize}px</span>
            </div>
            <input
              type="range"
              min={8}
              max={140}
              step={1}
              value={eraseBrushSize}
              onChange={(event) => onEraseBrushSizeChange?.(Number(event.target.value))}
              disabled={eraserMode !== "pixel_erase"}
              className="w-full accent-[#FFB36A]"
              aria-label="Erase brush size"
            />
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                className="h-[30px] rounded-md border border-[#D8C9B8] bg-white px-3 text-[11px] font-semibold text-[#5C4D42] transition-colors hover:bg-[#FBF7F1] disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => onClearEraseLayer?.()}
                disabled={eraserMode !== "pixel_erase" || !canUsePixelErase}
              >
                Reset
              </button>
              <button
                type="button"
                className="h-[30px] rounded-md border border-[#D8C9B8] bg-white px-3 text-[11px] font-semibold text-[#5C4D42] transition-colors hover:bg-[#FBF7F1] disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => onSaveEraseDraft?.()}
                disabled={eraserMode !== "pixel_erase" || !hasUnsavedEraseChanges || isSavingEraseChanges || !canUsePixelErase}
              >
                Save
              </button>
              <button
                type="button"
                className="h-[30px] rounded-md border border-[#D8C9B8] bg-[#FFF1D4] px-3 text-[11px] font-semibold text-[#5C4D42] transition-colors hover:bg-[#ffe9bf] disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => onConfirmEraseDraft?.()}
                disabled={eraserMode !== "pixel_erase" || !hasSavedEraseDraft || isSavingEraseChanges || !canUsePixelErase}
              >
                {isSavingEraseChanges ? "Saving" : "Confirm"}
              </button>
            </div>
            <p className="text-[10.5px] font-semibold leading-relaxed text-[#857C72]">
              Paint on the inpainted pixels, Save the edit, then Confirm to replace the current inpainted image.
            </p>
          </section>
        </div>
      </div>

      <div
        className={cn(
          "absolute top-[56px] z-20 w-[240px] rounded-[16px] border border-white/60 bg-white/80 px-4 py-3.5 shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15),0_0_0_1px_rgba(0,0,0,0.03)] backdrop-blur-2xl transition-all duration-300 ease-out origin-top",
          flyoutPositionClass,
          isPenActive && isFlyoutOpen 
            ? "opacity-100 scale-100 translate-x-0 pointer-events-auto" 
            : "opacity-0 scale-95 pointer-events-none",
          !(isPenActive && isFlyoutOpen) && flyoutSide === "left" && "translate-x-3",
          !(isPenActive && isFlyoutOpen) && flyoutSide === "right" && "-translate-x-3",
        )}
        role="group"
        aria-label="Pen tool options"
        aria-hidden={!(isPenActive && isFlyoutOpen)}
      >
        <div className="mb-3 flex items-center justify-between border-b border-[#F0EAE5] pb-2.5">
          <p className="text-[13px] font-bold tracking-tight text-[#2F2923]">Pen Options</p>
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-[3px] text-[9.5px] font-bold uppercase tracking-wider text-emerald-600 ring-1 ring-inset ring-emerald-500/20 shadow-[0_2px_4px_rgba(16,185,129,0.05)]">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)] animate-pulse" />
            Active
          </span>
        </div>

          <div className="space-y-3">
            <section>
              <p className="mb-2 text-[11px] font-semibold text-[#4A4138]">1. Draw shape</p>
              <div className="flex flex-wrap items-center gap-[6px]">
                <button
                  type="button"
                  className={chipClass(penShape === "box")}
                  onClick={() => setPenShape("box")}
                  aria-pressed={penShape === "box"}
                >
                  Box
                </button>
                <button
                  type="button"
                  className={chipClass(penShape === "polygon")}
                  onClick={() => setPenShape("polygon")}
                  aria-pressed={penShape === "polygon"}
                >
                  Polygon
                </button>
              </div>
            </section>

            <section>
              <p className="mb-2 text-[11px] font-semibold text-[#4A4138]">2. Use as</p>
              <div className="flex flex-wrap items-center gap-[6px]">
                <button
                  type="button"
                  className={targetChipClass("panel", penTarget === "panel")}
                  onClick={() => setPenTarget("panel")}
                  aria-pressed={penTarget === "panel"}
                  disabled={!penShape}
                >
                  Panel
                </button>
                <button
                  type="button"
                  className={targetChipClass("balloon", penTarget === "balloon")}
                  onClick={() => setPenTarget("balloon")}
                  aria-pressed={penTarget === "balloon"}
                  disabled={!penShape}
                >
                  Balloon
                </button>
                <button
                  type="button"
                  className={targetChipClass("text", penTarget === "text")}
                  onClick={() => setPenTarget("text")}
                  aria-pressed={penTarget === "text"}
                  disabled={!penShape}
                >
                  Text
                </button>
              </div>
            </section>
          </div>

          <p className="mt-4 text-[10.5px] font-semibold leading-relaxed text-[#857C72]">
            {penShape
              ? `Flow: choose your output target and start drawing ${penShape === "box" ? "a rectangle" : "points"} on the canvas.`
              : "Pick a shape pattern first to unlock an output mode."}
          </p>
        </div>
    </div>
  );
}
