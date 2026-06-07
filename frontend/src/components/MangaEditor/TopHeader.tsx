import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import {
  ChevronDown,
  ChevronRight,
  Home,
  Plus,
  SlidersHorizontal,
  Upload,
  FileDown,
} from "lucide-react";

import { useEditorStore } from "../../store/useEditorStore";
import type { InpaintSettings, TranslationSettings } from "../../store/useEditorStore";
import { cn } from "../../lib/utils";

interface ChapterOption {
  id: string;
  title: string;
  chapter_number: number;
}

interface TopHeaderProps {
  onUploadPages: (files: FileList | File[]) => void;
  isUploadingPages: boolean;
  uploadError?: string | null;
  uploadNotice?: string | null;
  onExportPsd?: () => void;
  onExportImage?: (format: "png" | "jpg" | "webp" | "pdf") => void;
  isExportingPsd?: boolean;
  isExportingImage?: boolean;
  exportError?: string | null;
  exportNotice?: string | null;
  chapters: ChapterOption[];
  activeChapterId?: string;
  onChapterChange: (chapterId: string) => void;
  onCreateChapter: () => void;
  isCreatingChapter: boolean;
  onRunMaskInference?: () => void;
  isRunningMaskInference?: boolean;
  onRunOCR?: () => void;
  isRuningOCR? : boolean
  onSaveMasks?: () => void;
  isSavingMasks?: boolean;
  hasDirtyMasks?: boolean;
  jobPhase?: "idle" | "submitting" | "pending" | "running" | "completed" | "failed";
  jobDetail?: string | null;
  // Pipeline gating
  allowRunOCR?: boolean;
  allowRunInpaint?: boolean;
  allowRunTranslate?: boolean;
  onRunInpaint?: () => void;
  isRunningInpaint?: boolean;
  onRunTranslate?: () => void;
  isRunningTranslate?: boolean;
  inpaintSettings?: InpaintSettings;
  onInpaintSettingsChange?: (patch: Partial<InpaintSettings>) => void;
  translationSettings?: TranslationSettings;
  onTranslationSettingsChange?: (patch: Partial<TranslationSettings>) => void;
}

const workflowSteps = ["Mask", "OCR","Inpaint","Translate"] as const;

function actionButtonLabel(
  isRunning: boolean,
  jobPhase: string,
  defaultLabel: string,
): string {
  if (!isRunning) return defaultLabel;
  if (jobPhase === "pending") return "Queued...";
  if (jobPhase === "running") return "Processing...";
  return "Running...";
}

export default function TopHeader({
  onUploadPages,
  isUploadingPages,
  uploadError,
  uploadNotice,
  onExportPsd,
  onExportImage,
  isExportingPsd = false,
  isExportingImage = false,
  exportError,
  exportNotice,
  chapters,
  activeChapterId,
  onChapterChange,
  onCreateChapter,
  isCreatingChapter,
  onRunMaskInference,
  isRunningMaskInference = false,
  onRunOCR,
  isRuningOCR = false,
  allowRunOCR = true,
  allowRunInpaint = true,
  allowRunTranslate = true,
  onRunInpaint,
  isRunningInpaint = false,
  onRunTranslate,
  isRunningTranslate = false,
  inpaintSettings = {
    method: "telea",
    radius: 5,
    ai_expand_strength: 0.2,
    text_expand_px: 0,
    balloon_safe_inset_mode: "auto",
    balloon_safe_inset_px: 4,
    clip_fallback_mode: "no_clip",
  },
  onInpaintSettingsChange = () => undefined,
  translationSettings = {
    enable_thinking: true,
  },
  onTranslationSettingsChange = () => undefined,
  onSaveMasks,
  isSavingMasks = false,
  hasDirtyMasks = false,
  jobPhase = "idle",
  jobDetail = null,
}: TopHeaderProps) {
  const { viewMode, setViewMode, activeWorkflow, setActiveWorkflow } = useEditorStore();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const inpaintPopoverRef = useRef<HTMLDivElement | null>(null);
  const [isInpaintPanelOpen, setIsInpaintPanelOpen] = useState(false);
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement | null>(null);

  const pillBase =
    "inline-flex h-[30px] shrink-0 items-center whitespace-nowrap rounded-full px-[12px] font-caption text-[11px] leading-none transition-all";
  const pillClass = (isActive: boolean, isPast: boolean, disabled?: boolean) =>
    cn(
      pillBase,
      isActive
        ? "border border-brand-border-goldLight bg-brand-gold-muted font-bold tracking-[0.06em] text-brand-text-step shadow-[0_4px_10px_rgba(217,174,47,0.14)]"
        : isPast
        ? "bg-white font-medium text-brand-text-muted"
        : "bg-[#FFF1DF] font-medium text-brand-text-muted hover:text-brand-text",
      disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
    );

  const triggerUploadPicker = () => uploadInputRef.current?.click();

  const inpaintSummary = useMemo(() => {
    const methodLabel = inpaintSettings.method === "ns" ? "Navier" : "Telea";
    const insetLabel =
      inpaintSettings.balloon_safe_inset_mode === "manual"
        ? `Inset ${Math.max(0, Math.round(inpaintSettings.balloon_safe_inset_px ?? 0))}px`
        : "Inset Auto";
    const growLabel = `Grow ${Math.max(0, Math.round(inpaintSettings.text_expand_px ?? 0))}px`;
    return `${methodLabel} · R${Math.max(1, Math.round(inpaintSettings.radius))} · ${growLabel} · ${insetLabel}`;
  }, [inpaintSettings]);

  useEffect(() => {
    if (activeWorkflow !== "Inpaint") {
      setIsInpaintPanelOpen(false);
    }
  }, [activeWorkflow]);

  useEffect(() => {
    if (!isInpaintPanelOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!inpaintPopoverRef.current) return;
      const target = event.target;
      if (target instanceof Node && inpaintPopoverRef.current.contains(target)) return;
      setIsInpaintPanelOpen(false);
    };

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [isInpaintPanelOpen]);

  useEffect(() => {
    if (!isExportMenuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!exportMenuRef.current) return;
      const target = event.target;
      if (target instanceof Node && exportMenuRef.current.contains(target)) return;
      setIsExportMenuOpen(false);
    };

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [isExportMenuOpen]);

  const handleUploadChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) onUploadPages(files);
    event.target.value = "";
  };

  const activeNotice = exportNotice ?? uploadNotice;
  const activeError = exportError ?? uploadError;

  return (
    <header className="relative z-40 flex-none bg-white">
      <div className="flex h-11 items-center justify-between border-b border-brand-border-warm px-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex min-w-0 items-center gap-1.5">
            <Link
              to="/dashboard"
              className="inline-flex shrink-0 items-center gap-1 text-[11px] font-semibold text-brand-text-muted transition-colors hover:text-brand-text"
              aria-label="Go back to dashboard"
            >
              <Home className="h-3.5 w-3.5 text-[#FF8533]" strokeWidth={1.8} />
              <span className="font-caption">Home</span>
            </Link>
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#888888]" strokeWidth={1.7} />
            <span className="truncate font-serif text-[20px] font-semibold tracking-[-0.02em] text-brand-text">
              Curator
            </span>
          </div>

          <div className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[#F0DEC7] bg-brand-surface-cream p-[2px]">
            {(["Original", "Translated"] as const).map((mode) => {
              const isActive = viewMode === mode;

              return (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={cn(
                    "rounded-full px-[10px] py-[5px] font-caption text-[11px] transition-all",
                    isActive
                      ? "border border-[#FFD8C4] bg-white font-semibold text-brand-text"
                      : "bg-[#FFF1DF] font-medium text-brand-text-muted hover:text-brand-text",
                  )}
                >
                  {mode}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div ref={exportMenuRef} className="relative inline-flex items-center">
            <button
              onClick={() => setIsExportMenuOpen((prev) => !prev)}
              disabled={isExportingPsd || isExportingImage}
              className="inline-flex h-[28px] items-center justify-center gap-1.5 rounded-full border border-brand-border-gold bg-brand-surface-yellow px-[10px] font-caption text-[11px] font-bold text-brand-text-goldBadge shadow-[0_4px_10px_rgba(214,178,71,0.15)] transition-colors hover:bg-[#fff2be] disabled:opacity-50"
            >
              <FileDown className="h-3.5 w-3.5" strokeWidth={1.9} />
              {(isExportingPsd || isExportingImage) ? "Exporting..." : "Export"}
              <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.9} />
            </button>
            {isExportMenuOpen ? (
              <div className="absolute right-0 top-[calc(100%+6px)] z-[90] min-w-[130px] rounded-[10px] border border-[#E8DCCA] bg-white p-1.5 shadow-[0_12px_24px_rgba(0,0,0,0.12)]">
                {(["psd", "png", "jpg", "webp", "pdf"] as const).map((format) => (
                  <button
                    key={format}
                    type="button"
                    onClick={() => {
                      setIsExportMenuOpen(false);
                      if (format === "psd") onExportPsd?.();
                      else onExportImage?.(format);
                    }}
                    className="flex w-full items-center justify-start rounded-[8px] px-2.5 py-1.5 font-caption text-[11px] font-semibold text-[#3B342C] hover:bg-[#FFF1DF]"
                  >
                    Export {format.toUpperCase()}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <input
            ref={uploadInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            className="hidden"
            onChange={handleUploadChange}
          />
          <button
            onClick={triggerUploadPicker}
            disabled={isUploadingPages}
            className="inline-flex h-[28px] items-center justify-center gap-1.5 rounded-full border border-brand-border-gold bg-brand-surface-yellow px-[10px] font-caption text-[11px] font-bold text-brand-text-goldBadge shadow-[0_4px_10px_rgba(214,178,71,0.15)] transition-colors hover:bg-[#fff2be] disabled:opacity-50"
          >
            <Upload className="h-3.5 w-3.5" strokeWidth={1.9} />
            {isUploadingPages ? "Uploading..." : "Upload"}
          </button>
        </div>
      </div>

      <div className="grid min-h-[58px] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 border-b border-brand-border-warm px-4 py-2.5">
        <div className="flex shrink-0 items-center gap-3">
            <div className="relative">
              <select
                value={activeChapterId ?? ""}
                onChange={(event) => onChapterChange(event.target.value)}
                className="h-[36px] w-[260px] appearance-none rounded-[12px] border border-[#E8DCCA] bg-white pl-3 pr-8 font-sans text-[11px] font-semibold leading-none text-[#241B17] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                aria-label="Select chapter"
              >
                {chapters.length > 0 ? (
                  chapters.map((chapter) => (
                    <option key={chapter.id} value={chapter.id}>
                      Ch.{chapter.chapter_number} - {chapter.title}
                    </option>
                  ))
                ) : (
                  <option value="">No chapter</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-brand-text-workflow" />
            </div>

            <button
              onClick={onCreateChapter}
              disabled={isCreatingChapter}
              className="inline-flex h-[36px] w-[36px] items-center justify-center rounded-[12px] border border-[#E8DCCA] bg-brand-surface-yellowBadge text-[#7D6B3D] transition-colors hover:bg-[#fff2cf] disabled:opacity-50"
              aria-label="Create chapter"
            >
              <Plus className="h-3.5 w-3.5" strokeWidth={1.9} />
            </button>
        </div>

        <div className="flex min-w-0 items-center justify-center">
          <div className="scrollbar-hide inline-flex max-w-full items-center gap-1 overflow-x-auto rounded-full border border-[#F0DEC7] bg-brand-surface-yellowLight p-[4px]">
            {workflowSteps.map((step) => {
              const isActive = activeWorkflow === step;
              const isPast =
                workflowSteps.indexOf(step) <
                workflowSteps.indexOf(activeWorkflow as (typeof workflowSteps)[number]);

              let disabled = false;
              if (step === "OCR" && !allowRunOCR) disabled = true;
              if (step === "Inpaint" && !allowRunInpaint) disabled = true;
              if (step === "Translate" && !allowRunTranslate) disabled = true;

              return (
                <button
                  key={step}
                  onClick={() => {
                    if (!disabled) setActiveWorkflow(step);
                  }}
                  className={pillClass(isActive, isPast, disabled)}
                  aria-disabled={disabled}
                  disabled={disabled}
                >
                  {step}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 justify-self-end">
            {activeWorkflow === "Mask" && hasDirtyMasks ? (
              <button
                onClick={onSaveMasks}
                disabled={isSavingMasks}
                className="hidden h-[28px] items-center justify-center rounded-full border border-[#E8DCCA] bg-white px-3 font-caption text-[11px] font-semibold text-[#241B17] shadow-sm lg:inline-flex"
                aria-label="Save edited masks"
              >
                {isSavingMasks ? "Saving..." : "Save"}
              </button>
            ) : null}

            {activeWorkflow === "Mask" && (
              <button
                onClick={onRunMaskInference}
                disabled={!onRunMaskInference || isRunningMaskInference}
                title={jobDetail ?? undefined}
                className="inline-flex h-[30px] items-center justify-center rounded-full border border-brand-border-yellowStrong bg-brand-gold px-[14px] font-caption text-[11px] font-bold text-brand-text-goldDark shadow-[0_5px_12px_rgba(217,174,47,0.17)] transition-colors hover:bg-[#f0c038] disabled:opacity-50"
              >
                {actionButtonLabel(isRunningMaskInference, jobPhase, "Run Mask")}
              </button>
            )}

            {activeWorkflow === "OCR" && (
              <button
                onClick={onRunOCR}
                disabled={!onRunOCR || isRuningOCR}
                title={jobDetail ?? undefined}
                className="inline-flex h-[30px] items-center justify-center rounded-full border border-brand-border-yellowStrong bg-brand-gold px-[14px] font-caption text-[11px] font-bold text-brand-text-goldDark shadow-[0_5px_12px_rgba(217,174,47,0.17)] transition-colors hover:bg-[#f0c038] disabled:opacity-50"
              >
                {actionButtonLabel(isRuningOCR, jobPhase, "Run OCR")}
              </button>
            )}
              {activeWorkflow === "Inpaint" && (
                <div ref={inpaintPopoverRef} className="relative flex items-center gap-1.5">
                  <span className="hidden h-[28px] items-center rounded-full border border-[#E8DCCA] bg-white px-3 font-caption text-[10px] font-semibold text-[#6E6357] md:inline-flex">
                    {inpaintSummary}
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsInpaintPanelOpen((prev) => !prev)}
                    className={cn(
                      "inline-flex h-[30px] items-center gap-1 rounded-full border px-3 font-caption text-[10px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold",
                      isInpaintPanelOpen
                        ? "border-brand-border-yellowStrong bg-[#FFF1D4] text-brand-text"
                        : "border-[#E8DCCA] bg-white text-[#3B342C] hover:bg-[#fff9f2]",
                    )}
                    aria-label="Adjust inpaint settings"
                    aria-expanded={isInpaintPanelOpen}
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5" strokeWidth={1.8} />
                    Adjust
                  </button>
                  <button
                    onClick={onRunInpaint}
                    disabled={!onRunInpaint || isRunningInpaint || !allowRunInpaint}
                    title={jobDetail ?? undefined}
                    className="inline-flex h-[30px] items-center justify-center rounded-full border border-brand-border-yellowStrong bg-brand-gold px-[14px] font-caption text-[11px] font-bold text-brand-text-goldDark shadow-[0_5px_12px_rgba(217,174,47,0.17)] transition-colors hover:bg-[#f0c038] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold disabled:opacity-50"
                  >
                    {actionButtonLabel(isRunningInpaint, jobPhase, "Run Inpaint")}
                  </button>

                  {isInpaintPanelOpen ? (
                    <div className="absolute right-0 top-[calc(100%+8px)] z-[80] w-[310px] rounded-[14px] border border-[#E8DCCA] bg-white p-3 shadow-[0_16px_34px_rgba(26,16,8,0.14)]">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <h4 className="font-caption text-[10px] font-bold uppercase tracking-[0.08em] text-[#8E6248]">
                          Inpaint Adjustments
                        </h4>
                        <button
                          type="button"
                          onClick={() =>
                            onInpaintSettingsChange({
                              method: "telea",
                              radius: 5,
                              ai_expand_strength: 0.2,
                              text_expand_px: 0,
                              balloon_safe_inset_mode: "auto",
                              balloon_safe_inset_px: 4,
                              clip_fallback_mode: "no_clip",
                            })
                          }
                          className="rounded-full border border-[#E8DCCA] bg-[#FFF8EF] px-2 py-0.5 font-caption text-[9px] font-semibold text-[#6A564A] hover:bg-[#fff2e1]"
                        >
                          Reset
                        </button>
                      </div>
                      <div className="mb-2 rounded-[10px] border border-[#F2DFC9] bg-[#FFF8EF] px-2.5 py-2 text-[10px] leading-relaxed text-[#6C594D]">
                        Recommended defaults: <span className="font-semibold text-[#4F4037]">Telea, Radius 5, AI Expand 20%, Text Grow 0px, Safe Inset Auto, Fallback No Clip</span>. AI Expand affects AI text regions only, while Text Grow dilates all text masks. Settings apply on the next Run Inpaint.
                      </div>

                      <div className="grid grid-cols-[105px_minmax(0,1fr)] items-center gap-x-2 gap-y-2.5">
                        <label htmlFor="inpaint-method" className="text-[10px] font-semibold text-[#5B4F45]">
                          Method
                        </label>
                        <select
                          id="inpaint-method"
                          aria-label="Inpaint method"
                          value={inpaintSettings.method}
                          onChange={(event) =>
                            onInpaintSettingsChange({
                              method: event.target.value as InpaintSettings["method"],
                            })
                          }
                          className="h-[30px] rounded-[10px] border border-[#E8DCCA] bg-white px-2 font-caption text-[10px] font-semibold text-[#241B17] outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                        >
                          <option value="telea">Telea</option>
                          <option value="ns">Navier-Stokes</option>
                        </select>

                        <label htmlFor="inpaint-radius" className="text-[10px] font-semibold text-[#5B4F45]">
                          Radius
                        </label>
                        <input
                          id="inpaint-radius"
                          aria-label="Inpaint radius"
                          type="number"
                          min={1}
                          max={20}
                          step={1}
                          value={inpaintSettings.radius}
                          onChange={(event) =>
                            onInpaintSettingsChange({
                              radius: Number(event.target.value || 1),
                            })
                          }
                          className="h-[30px] rounded-[10px] border border-[#E8DCCA] bg-white px-2 text-[10px] font-semibold text-[#241B17] outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                        />

                        <label htmlFor="inpaint-expand" className="text-[10px] font-semibold text-[#5B4F45]">
                          AI Expand
                        </label>
                        <div className="flex items-center gap-2 rounded-[10px] border border-[#E8DCCA] bg-[#FFFDF9] px-2 py-1">
                          <input
                            id="inpaint-expand"
                            aria-label="AI expand strength"
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={inpaintSettings.ai_expand_strength}
                            onChange={(event) =>
                              onInpaintSettingsChange({
                                ai_expand_strength: Number(event.target.value),
                              })
                            }
                            className="h-[16px] w-full accent-[#D9AE2F]"
                          />
                          <span className="w-8 text-right font-caption text-[9px] font-semibold text-[#6E6357]">
                            {Math.round(inpaintSettings.ai_expand_strength * 100)}%
                          </span>
                        </div>

                        <label htmlFor="inpaint-text-grow" className="text-[10px] font-semibold text-[#5B4F45]">
                          Text Grow
                        </label>
                        <div className="flex items-center gap-2 rounded-[10px] border border-[#E8DCCA] bg-[#FFFDF9] px-2 py-1">
                          <input
                            id="inpaint-text-grow"
                            aria-label="Text mask grow pixels"
                            type="range"
                            min={0}
                            max={40}
                            step={1}
                            value={inpaintSettings.text_expand_px ?? 0}
                            onChange={(event) =>
                              onInpaintSettingsChange({
                                text_expand_px: Number(event.target.value),
                              })
                            }
                            className="h-[16px] w-full accent-[#D9AE2F]"
                          />
                          <span className="w-10 text-right font-caption text-[9px] font-semibold text-[#6E6357]">
                            {Math.round(inpaintSettings.text_expand_px ?? 0)}px
                          </span>
                        </div>

                        <label htmlFor="inpaint-inset-mode" className="text-[10px] font-semibold text-[#5B4F45]">
                          Safe Inset
                        </label>
                        <div className="grid grid-cols-[minmax(0,1fr)_84px] gap-2">
                          <select
                            id="inpaint-inset-mode"
                            aria-label="Balloon inset mode"
                            value={inpaintSettings.balloon_safe_inset_mode}
                            onChange={(event) =>
                              onInpaintSettingsChange({
                                balloon_safe_inset_mode: event.target.value as InpaintSettings["balloon_safe_inset_mode"],
                              })
                            }
                            className="h-[30px] rounded-[10px] border border-[#E8DCCA] bg-white px-2 font-caption text-[10px] font-semibold text-[#241B17] outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                          >
                            <option value="auto">Auto</option>
                            <option value="manual">Manual</option>
                          </select>
                          <input
                            aria-label="Balloon inset pixels"
                            type="number"
                            min={0}
                            max={64}
                            step={1}
                            disabled={inpaintSettings.balloon_safe_inset_mode !== "manual"}
                            value={inpaintSettings.balloon_safe_inset_px}
                            onChange={(event) =>
                              onInpaintSettingsChange({
                                balloon_safe_inset_px: Number(event.target.value || 0),
                              })
                            }
                            className="h-[30px] rounded-[10px] border border-[#E8DCCA] bg-white px-2 text-[10px] font-semibold text-[#241B17] outline-none focus-visible:ring-2 focus-visible:ring-brand-gold disabled:cursor-not-allowed disabled:bg-[#F7F1E8] disabled:text-[#A49486]"
                          />
                        </div>

                        <label htmlFor="inpaint-fallback" className="text-[10px] font-semibold text-[#5B4F45]">
                          Fallback
                        </label>
                        <select
                          id="inpaint-fallback"
                          aria-label="Clip fallback mode"
                          value={inpaintSettings.clip_fallback_mode}
                          onChange={(event) =>
                            onInpaintSettingsChange({
                              clip_fallback_mode: event.target.value as InpaintSettings["clip_fallback_mode"],
                            })
                          }
                          className="h-[30px] rounded-[10px] border border-[#E8DCCA] bg-white px-2 font-caption text-[10px] font-semibold text-[#241B17] outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                        >
                          <option value="no_clip">No Clip</option>
                          <option value="inset_bbox">Inset BBox</option>
                        </select>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
              {activeWorkflow === "Translate" && (
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() =>
                      onTranslationSettingsChange({
                        enable_thinking: !translationSettings.enable_thinking,
                      })
                    }
                    className={cn(
                      "inline-flex h-[30px] items-center justify-center rounded-full border px-[12px] font-caption text-[10px] font-semibold transition-colors",
                      translationSettings.enable_thinking
                        ? "border-[#D6B247] bg-[#FFF2CC] text-[#5A4300]"
                        : "border-[#E8DCCA] bg-white text-[#4A4036]",
                    )}
                    title="Toggle model thinking mode for translation"
                  >
                    Thinking: {translationSettings.enable_thinking ? "On" : "Off"}
                  </button>
                  <button
                    onClick={onRunTranslate}
                    disabled={!onRunTranslate || isRunningTranslate || !allowRunTranslate}
                    title={jobDetail ?? undefined}
                    className="inline-flex h-[30px] items-center justify-center rounded-full border border-brand-border-yellowStrong bg-brand-gold px-[14px] font-caption text-[11px] font-bold text-brand-text-goldDark shadow-[0_5px_12px_rgba(217,174,47,0.17)] transition-colors hover:bg-[#f0c038] disabled:opacity-50"
                  >
                    {actionButtonLabel(isRunningTranslate, jobPhase, "Run Translate")}
                  </button>
                </div>
              )}
            
        </div>
      </div>

      {activeError || activeNotice ? (
        <div className="border-b border-brand-border-warm bg-brand-surface-alt px-4 py-1.5">
          <p className={cn("text-[10px]", activeError ? "text-red-700" : "text-brand-text-muted")}>
            {activeError ?? activeNotice}
          </p>
        </div>
      ) : null}
    </header>
  );
}
