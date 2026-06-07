import { useEffect, useMemo, useRef, useState } from "react";
import type { PageText } from "../../types/api";
import OCRBlock from "./OCRBlock";
import { cn } from "../../lib/utils";
import { resolveTranslatedText } from "../../lib/textDisplay";

export interface OcrSidebarItem {
  text: PageText;
  title: string;
  orderLabel: string;
}

const FONT_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "Komika", value: "\"Komika Text\", \"Comic Sans MS\", \"Trebuchet MS\", sans-serif" },
  { label: "Manga Serif", value: "\"Noto Serif JP\", \"Yu Mincho\", \"Hiragino Mincho ProN\", serif" },
  { label: "Clean Sans", value: "\"Inter\", \"Segoe UI\", \"Helvetica Neue\", Arial, sans-serif" },
  { label: "Handwritten", value: "\"Patrick Hand\", \"Comic Sans MS\", cursive" },
];

interface RightSidebarProps {
  items: OcrSidebarItem[];
  activeWorkflow?: string;
  onTextChange: (textId: string, value: string) => void;
  viewMode: "Original" | "Translated";
  textScaleByTextId?: Record<string, number>;
  onTextScaleChange?: (textId: string, nextScale: number) => void;
  textColorByTextId?: Record<string, string>;
  defaultTextColor?: string;
  onTextColorChange?: (textId: string, color: string) => void;
  textFontByTextId?: Record<string, string>;
  defaultTextFont?: string;
  onTextFontChange?: (textId: string, fontFamily: string) => void;
  textFontWeightByTextId?: Record<string, "normal" | "bold">;
  defaultTextFontWeight?: "normal" | "bold";
  onTextFontWeightChange?: (textId: string, fontWeight: "normal" | "bold") => void;
  placementModeByRegionId?: Record<string, "auto" | "manual">;
  onResetLayout?: (textId: string, regionId: string) => void;
  selectedRegionId?: string | null;
  onSelectRegion?: (regionId: string) => void;
  saveState: "idle" | "dirty" | "saving" | "saved" | "error";
  onToggleApprove?: (textId: string, approved: boolean) => void;
}

export default function RightSidebar({
  items,
  activeWorkflow = "OCR",
  onTextChange,
  viewMode,
  textScaleByTextId = {},
  onTextScaleChange,
  textColorByTextId = {},
  defaultTextColor = "#111111",
  onTextColorChange,
  textFontByTextId = {},
  defaultTextFont = FONT_OPTIONS[0]!.value,
  onTextFontChange,
  textFontWeightByTextId = {},
  defaultTextFontWeight = "normal",
  onTextFontWeightChange,
  placementModeByRegionId = {},
  onResetLayout,
  selectedRegionId = null,
  onSelectRegion,
  saveState,
}: RightSidebarProps) {
  const [sidebarMode, setSidebarMode] = useState<"blocks" | "flow">("blocks");
  const [focusMode, setFocusMode] = useState<"block" | "page">("block");
  const [activeRegionId, setActiveRegionId] = useState<string | null>(selectedRegionId);
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    const fallbackRegionId = items[0]?.text.region_id ?? null;
    const nextFromParent = selectedRegionId ?? fallbackRegionId;
    setActiveRegionId((prev) => (prev === nextFromParent ? prev : nextFromParent));
  }, [items, selectedRegionId]);

  const selectedIndex = useMemo(() => {
    const index = items.findIndex(({ text }) => text.region_id === activeRegionId);
    if (index >= 0) return index;
    return items.length > 0 ? 0 : -1;
  }, [activeRegionId, items]);

  const selectedItem =
    selectedIndex >= 0 ? items[selectedIndex] : null;
  const selectedText = selectedItem?.text ?? null;
  const selectedTextId = selectedText?.id ?? null;
  const selectedRegionColor = selectedText
    ? (textColorByTextId[selectedText.id] ?? defaultTextColor)
    : defaultTextColor;
  const selectedRegionFont = selectedText
    ? (textFontByTextId[selectedText.id] ?? defaultTextFont)
    : defaultTextFont;
  const selectedScale = selectedTextId ? (textScaleByTextId[selectedTextId] ?? 1) : 1;
  const selectedFontWeight = selectedTextId
    ? (textFontWeightByTextId[selectedTextId] ?? defaultTextFontWeight)
    : defaultTextFontWeight;
  const selectedPlacementMode = selectedText
    ? (placementModeByRegionId[selectedText.region_id] ?? "auto")
    : "auto";
  const sourceText = (selectedText?.ocr_text_corrected ?? selectedText?.ocr_text_raw ?? "").trim();
  const finalText = selectedText ? resolveTranslatedText(selectedText).trim() : "";
  const selectedInputValue = selectedText
    ? typeof selectedText.display_text_final === "string"
      ? selectedText.display_text_final
      : typeof selectedText.translation_corrected === "string"
        ? selectedText.translation_corrected
        : selectedText.translation_draft ?? ""
    : "";
  const selectedTranslationState = selectedText
    ? (selectedText.display_text_final ?? "").trim() || (selectedText.translation_corrected ?? "").trim()
      ? "Manual"
      : (selectedText.translation_draft ?? "").trim()
        ? "Draft"
        : "Empty"
    : "Empty";
  const charCount = finalText.length;
  const isMaskWorkflow = activeWorkflow === "Mask";
  const sidebarDescription = isMaskWorkflow
    ? "Mask editing controls are available directly on the canvas."
    : viewMode === "Translated"
      ? "Review and polish the final dialogue sequence."
      : "Correct raw predictions to keep dialogue cleanup consistent.";

  const applyScaleToPage = (nextScale: number) => {
    if (!onTextScaleChange) return;
    for (const { text } of items) {
      onTextScaleChange(text.id, nextScale);
    }
  };

  const applyPreset = (preset: "dialogue" | "whisper" | "shout") => {
    const presetScale = preset === "whisper" ? 0.9 : preset === "shout" ? 1.2 : 1;
    if (focusMode === "page") {
      applyScaleToPage(presetScale);
      return;
    }
    if (selectedTextId && onTextScaleChange) {
      onTextScaleChange(selectedTextId, presetScale);
    }
  };

  const applyColor = (nextColor: string) => {
    if (!onTextColorChange || items.length === 0) return;
    if (focusMode === "page") {
      for (const { text } of items) {
        onTextColorChange(text.id, nextColor);
      }
      return;
    }
    if (selectedText) {
      onTextColorChange(selectedText.id, nextColor);
    }
  };

  const applyFont = (fontFamily: string) => {
    if (!onTextFontChange || items.length === 0) return;
    if (focusMode === "page") {
      for (const { text } of items) {
        onTextFontChange(text.id, fontFamily);
      }
      return;
    }
    if (selectedText) {
      onTextFontChange(selectedText.id, fontFamily);
    }
  };

  const applyFontWeight = (fontWeight: "normal" | "bold") => {
    if (!onTextFontWeightChange || items.length === 0) return;
    if (focusMode === "page") {
      for (const { text } of items) {
        onTextFontWeightChange(text.id, fontWeight);
      }
      return;
    }
    if (selectedText) {
      onTextFontWeightChange(selectedText.id, fontWeight);
    }
  };

  const navigateSelection = (
    delta: number,
    options?: { anchorTextId?: string; focusInput?: boolean },
  ) => {
    if (!onSelectRegion || items.length === 0) return;
    const anchorIndex = options?.anchorTextId
      ? items.findIndex(({ text }) => text.id === options.anchorTextId)
      : selectedIndex;
    const from = anchorIndex >= 0 ? anchorIndex : 0;
    const to = Math.max(0, Math.min(items.length - 1, from + delta));
    if (to === from) return;

    const next = items[to];
    if (!next) return;
    setActiveRegionId(next.text.region_id);
    onSelectRegion(next.text.region_id);

    if (options?.focusInput) {
      inputRefs.current[next.text.id]?.focus();
      requestAnimationFrame(() => {
        inputRefs.current[next.text.id]?.focus();
      });
    }
  };

  return (
    <aside className="z-20 flex h-full w-full shrink-0 flex-[0_0_320px] flex-col overflow-hidden border-l border-[#FFD9C6] bg-[#FFF4EC] shadow-[-8px_0_24px_rgba(0,0,0,0.02)] xl:flex-[0_0_340px]">
      <div className="custom-scrollbar min-h-0 w-full flex-[1_1_auto] overflow-y-auto">
        <div className="flex flex-col gap-[18px] px-6 py-[26px]">
          <div className="mb-2 flex flex-col gap-1.5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-serif text-[22px] leading-none tracking-tight text-brand-text">
                Intelligence Utilities
              </h2>
              <span className="flex items-center justify-center whitespace-nowrap rounded-full border border-[#E9D7C7] bg-[#FFF8F1] px-2 py-[3px] font-caption text-[9px] font-bold tracking-wide text-brand-text-muted shadow-sm">
                {saveState}
              </span>
            </div>
            <p className="pr-4 pt-1.5 text-[11.5px] font-medium leading-relaxed text-brand-text-muted">
              {sidebarDescription}
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex gap-1 rounded-lg bg-black/5 p-1">
              <button
                onClick={() => setSidebarMode("blocks")}
                className={cn(
                  "flex-1 rounded-md py-1.5 text-[11px] font-bold transition-all",
                  sidebarMode === "blocks"
                    ? "bg-white text-brand-text shadow-sm"
                    : "text-brand-text-muted hover:text-brand-text",
                )}
              >
                Detailed Blocks
              </button>
              <button
                onClick={() => setSidebarMode("flow")}
                className={cn(
                  "flex-1 rounded-md py-1.5 text-[11px] font-bold transition-all",
                  sidebarMode === "flow"
                    ? "bg-white text-brand-text shadow-sm"
                    : "text-brand-text-muted hover:text-brand-text",
                )}
              >
                Reading Flow
              </button>
            </div>

            {sidebarMode === "blocks" ? (
              <>
                {isMaskWorkflow ? (
                  <div className="rounded-[12px] border border-[#F1DDD0] bg-white p-5 text-[11px] font-medium leading-relaxed text-brand-text-muted shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                    Use the mask toolbar on the canvas to review, draw, edit, or erase mask regions.
                  </div>
                ) : viewMode === "Translated" ? (
                  <div className="flex flex-col gap-2.5">
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        onClick={() => setFocusMode("block")}
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-[9px] font-bold transition-colors",
                          focusMode === "block"
                            ? "border-[#E8B873] bg-[#FFE0B2] text-[#5A3E1F]"
                            : "border-[#DED0C2] bg-white text-[#746252]",
                        )}
                      >
                        Block Focus
                      </button>
                      <button
                        type="button"
                        onClick={() => setFocusMode("page")}
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-[9px] font-bold transition-colors",
                          focusMode === "page"
                            ? "border-[#E8B873] bg-[#FFE0B2] text-[#5A3E1F]"
                            : "border-[#DED0C2] bg-white text-[#746252]",
                        )}
                      >
                        Page Defaults
                      </button>
                    </div>

                    {selectedText ? (
                      <>
                        <div className="flex flex-col gap-2 rounded-[12px] border border-[#E5D8CC] bg-white p-3 shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                          <div className="flex items-center justify-between gap-2">
                            <h4 className="text-[11px] font-bold text-[#3A2E24]">
                              Selected Block
                            </h4>
                            <div className="flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => navigateSelection(-1)}
                                disabled={selectedIndex <= 0}
                                className="h-5 w-5 rounded border border-[#D9CBBB] bg-white text-[10px] font-bold text-[#5C4B3D] disabled:opacity-40"
                                aria-label="Previous block"
                              >
                                ←
                              </button>
                              <button
                                type="button"
                                onClick={() => navigateSelection(1)}
                                disabled={selectedIndex >= items.length - 1}
                                className="h-5 w-5 rounded border border-[#D9CBBB] bg-white text-[10px] font-bold text-[#5C4B3D] disabled:opacity-40"
                                aria-label="Next block"
                              >
                                →
                              </button>
                              <span className="rounded-full border border-[#E9D7C7] bg-[#FFF0DE] px-2 py-0.5 text-[9px] font-bold text-[#9A5E37]">
                                {selectedItem?.orderLabel ?? "..."}
                              </span>
                            </div>
                          </div>
                          <div className="text-[9px] font-bold text-[#8C7A6A]">Source JP</div>
                          <div className="rounded-[8px] border border-[#E8DED2] bg-[#FBF8F3] px-2.5 py-1.5 text-[10px] text-[#6F6258] whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                            {sourceText || "No source text available"}
                          </div>
                          <div className="text-[9px] font-bold text-[#8C7A6A]">
                            <span>Final Translation</span>
                            <span className="ml-2 rounded-full border border-[#E3D5C8] bg-[#FBF8F3] px-2 py-0.5 text-[8px] font-bold text-[#5C4B3D]">
                              {selectedTranslationState}
                            </span>
                          </div>
                          <input
                            type="text"
                            value={selectedInputValue}
                            onChange={(event) => onTextChange(selectedText.id, event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "ArrowDown") {
                                event.preventDefault();
                                navigateSelection(1);
                              } else if (event.key === "ArrowUp") {
                                event.preventDefault();
                                navigateSelection(-1);
                              }
                            }}
                            className="h-8 w-full rounded-[8px] border border-[#D7C8BA] bg-white px-2.5 text-[10px] font-semibold text-[#2C221A] focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-gold"
                            aria-label="Final Translation"
                          />
                          <div className="flex items-center justify-between text-[8.5px] font-semibold text-[#907A67]">
                            <span>Source locked</span>
                            <span>{charCount} chars</span>
                          </div>
                          <div className="flex items-center justify-between rounded-[8px] border border-[#E8DED2] bg-[#FBF8F3] px-2.5 py-1.5">
                            <span className="text-[8.5px] font-semibold text-[#7E6C5B]">Layout state</span>
                            <span className="rounded-full border border-[#E3D5C8] bg-white px-2 py-0.5 text-[8px] font-bold text-[#5C4B3D]">
                              {selectedPlacementMode === "manual" ? "Manual moved" : "Auto seeded"}
                            </span>
                          </div>
                          <div className="text-[8.5px] text-[#8C7A69]">
                            Tip: Keep balloon text concise. Aim for 1-2 lines.
                          </div>
                        </div>

                        <div className="flex flex-col gap-2 rounded-[12px] border border-[#E5D8CC] bg-white p-3 shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                          <h4 className="text-[11px] font-bold text-[#3A2E24]">Typography</h4>
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-semibold text-[#7F7062]">Font family</span>
                            <span className="rounded-full border border-[#E1D4C7] bg-[#F8F3EC] px-2 py-0.5 text-[9px] font-bold text-[#493B2F]">
                              {FONT_OPTIONS.find((font) => font.value === selectedRegionFont)?.label ?? "Custom"}
                            </span>
                          </div>
                          <select
                            value={selectedRegionFont}
                            onChange={(event) => applyFont(event.target.value)}
                            className="h-7 w-full rounded-[8px] border border-[#D7C8BA] bg-white px-2 text-[10px] font-semibold text-[#2C221A] focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-gold"
                            aria-label="Typography Font Family"
                          >
                            {FONT_OPTIONS.map((font) => (
                              <option key={font.value} value={font.value}>
                                {font.label}
                              </option>
                            ))}
                          </select>
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-semibold text-[#7F7062]">Size</span>
                            <span className="text-[9px] font-bold text-[#3A2E24]">
                              {Math.round(selectedScale * 100)}%
                            </span>
                          </div>
                          <input
                            type="range"
                            min={0.6}
                            max={2}
                            step={0.05}
                            value={selectedScale}
                            onChange={(event) => {
                              const next = Number(event.target.value);
                              if (focusMode === "page") {
                                applyScaleToPage(next);
                              } else if (selectedTextId && onTextScaleChange) {
                                onTextScaleChange(selectedTextId, next);
                              }
                            }}
                            className="h-1 w-full accent-[#F4B287]"
                            aria-label="Typography Size"
                          />
                          <div className="flex flex-wrap gap-1.5">
                            <button
                              type="button"
                              onClick={() => applyFontWeight("normal")}
                              className={cn(
                                "rounded-full border px-2 py-0.5 text-[8.5px] font-semibold transition-colors",
                                selectedFontWeight === "normal"
                                  ? "border-[#E0B46B] bg-[#FFD28A] text-[#3A2E24]"
                                  : "border-[#E3D5C8] bg-[#F6EFE6] text-[#6B5A4A] hover:bg-white",
                              )}
                              aria-pressed={selectedFontWeight === "normal"}
                            >
                              Regular
                            </button>
                            <button
                              type="button"
                              onClick={() => applyFontWeight("bold")}
                              className={cn(
                                "rounded-full border px-2 py-0.5 text-[8.5px] font-bold transition-colors",
                                selectedFontWeight === "bold"
                                  ? "border-[#E0B46B] bg-[#FFD28A] text-[#3A2E24]"
                                  : "border-[#E3D5C8] bg-[#F6EFE6] text-[#6B5A4A] hover:bg-white",
                              )}
                              aria-pressed={selectedFontWeight === "bold"}
                            >
                              Bold
                            </button>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-semibold text-[#7F7062]">Color</span>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[9px] font-bold text-[#3A2E24]">
                                {selectedRegionColor.toUpperCase()}
                              </span>
                              <span
                                className="h-3.5 w-3.5 rounded-full border border-[#D3C2B2]"
                                style={{ backgroundColor: selectedRegionColor }}
                              />
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {["#111111", "#FFFFFF", "#FACC15", "#FB7185", "#38BDF8", "#22C55E"].map((color) => (
                              <button
                                key={color}
                                type="button"
                                aria-label={`Set text color ${color}`}
                                onClick={() => applyColor(color)}
                                className={cn(
                                  "h-5 w-5 rounded-full border transition-transform hover:scale-105",
                                  selectedRegionColor.toLowerCase() === color.toLowerCase()
                                    ? "border-[#5A3E1F] ring-1 ring-[#E8B873]"
                                    : "border-[#D9CBBB]",
                                )}
                                style={{ backgroundColor: color }}
                              />
                            ))}
                            <input
                              type="color"
                              value={selectedRegionColor}
                              onChange={(event) => applyColor(event.target.value)}
                              className="h-5 w-7 cursor-pointer rounded border border-[#D9CBBB] bg-white p-0.5"
                              aria-label="Custom text color"
                            />
                          </div>
                          <div className="text-[8.5px] text-[#8B7A69]">
                            Pick white or bright colors for dark balloons.
                          </div>
                        </div>

                        <div className="flex gap-2">
                          <button
                            type="button"
                            className="rounded-[8px] border border-[#E0B46B] bg-[#FFCB73] px-3 py-1.5 text-[9px] font-bold text-[#2C221A]"
                            onClick={() => {
                              if (!selectedText || !onResetLayout) return;
                              onResetLayout(selectedText.id, selectedText.region_id);
                            }}
                          >
                            Reset layout
                          </button>
                          <button
                            type="button"
                            className="rounded-[8px] border border-[#D9CBBB] bg-white px-3 py-1.5 text-[9px] font-bold text-[#4B3F33]"
                            onClick={() => applyScaleToPage(selectedScale)}
                          >
                            Apply to page
                          </button>
                        </div>

                        <div className="flex flex-col gap-2 rounded-[12px] border border-[#E5D8CC] bg-white p-3 shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                          <h4 className="text-[11px] font-bold text-[#3A2E24]">Quick Presets</h4>
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={() => applyPreset("dialogue")}
                              className="rounded-full border border-[#E1D4C7] bg-[#F8F3EC] px-2 py-0.5 text-[8.5px] font-semibold text-[#5C4B3D]"
                            >
                              Dialogue
                            </button>
                            <button
                              type="button"
                              onClick={() => applyPreset("whisper")}
                              className="rounded-full border border-[#E1D4C7] bg-[#F8F3EC] px-2 py-0.5 text-[8.5px] font-semibold text-[#5C4B3D]"
                            >
                              Whisper
                            </button>
                            <button
                              type="button"
                              onClick={() => applyPreset("shout")}
                              className="rounded-full border border-[#E1D4C7] bg-[#F8F3EC] px-2 py-0.5 text-[8.5px] font-semibold text-[#5C4B3D]"
                            >
                              Shout
                            </button>
                          </div>
                        </div>

                        <div className="flex items-center justify-between rounded-[8px] border border-[#EBD8BE] bg-[#FFF8EE] px-2.5 py-1 text-[8.5px] font-bold text-[#8B6B48]">
                          <span>{saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved · just now" : "Saved · 2 sec ago"}</span>
                          <span className="text-[#3D5D8E]">Undo</span>
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[10px] border border-dashed border-[#E9D7C7] bg-[#FFFDFB] px-4 py-6 text-center text-[11px] text-brand-text-muted">
                        No translated text blocks available yet.
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col gap-2 rounded-[12px] border border-brand-border-card bg-white p-4 shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="font-caption text-[10px] font-bold uppercase tracking-[0.08em] text-[#B16A4F]">
                          Work Queue
                        </h3>
                        <span className="font-caption text-[9px] font-bold text-brand-text-muted">
                          Autosave On
                        </span>
                      </div>
                      <span className="font-serif text-[18px] font-semibold leading-none text-brand-text">
                        {items.length} blocks loaded
                      </span>
                    </div>

                    <div className="flex flex-col gap-3 rounded-[12px] border border-[#F1DDD0] bg-white p-4 shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                      <div className="flex items-center justify-between gap-2">
                        <h4 className="font-serif text-[18px] font-semibold leading-none text-brand-text">
                          OCR Review
                        </h4>
                        <span className="rounded-full border border-[#E9D7C7] bg-[#FFF8F1] px-2.5 py-0.5 font-caption text-[9px] font-bold text-brand-text-muted">
                          {items.length} items
                        </span>
                      </div>

                      <div className="flex flex-col gap-2.5">
                        {items.length === 0 ? (
                          <div className="rounded-[10px] border border-dashed border-[#E9D7C7] bg-[#FFFDFB] px-4 py-6 text-center text-[11px] text-brand-text-muted">
                            No OCR text regions available.
                          </div>
                        ) : (
                          items.map(({ text, title, orderLabel }) => (
                            <OCRBlock
                              key={text.id}
                              title={title}
                              orderLabel={orderLabel}
                              sourceText={text.ocr_text_raw}
                              sourceLabel="Raw"
                              value={text.ocr_text_corrected ?? text.ocr_text_raw ?? ""}
                              onChange={(value) => onTextChange(text.id, value)}
                              onSelect={() => {
                                setActiveRegionId(text.region_id);
                                onSelectRegion?.(text.region_id);
                              }}
                              onNavigatePrevious={() =>
                                navigateSelection(-1, { anchorTextId: text.id, focusInput: true })
                              }
                              onNavigateNext={() =>
                                navigateSelection(1, { anchorTextId: text.id, focusInput: true })
                              }
                              inputRef={(node) => {
                                inputRefs.current[text.id] = node;
                              }}
                              active={activeRegionId === text.region_id}
                            />
                          ))
                        )}
                      </div>
                    </div>
                  </>
                )}
              </>
            ) : (
              <div className="flex flex-col gap-3 rounded-[12px] border border-[#F1DDD0] bg-white p-5 shadow-[0_8px_20px_rgba(0,0,0,0.04)]">
                <div className="mb-2">
                  <h4 className="font-serif text-[18px] font-semibold leading-none text-brand-text">
                    Story Flow
                  </h4>
                  <p className="mt-2 text-[10px] text-brand-text-muted italic">
                    Sequential preview of the entire page dialogue.
                  </p>
                </div>
                <div className="flex flex-col gap-4">
                  {items.map(({ text, orderLabel }) => {
                    const content =
                      viewMode === "Translated"
                        ? resolveTranslatedText(text)
                        : text.ocr_text_corrected ?? text.ocr_text_raw ?? "";

                    return (
                      <div
                        key={text.id}
                        className={cn(
                          "group relative min-w-0 cursor-pointer border-l-2 py-1 pl-4 transition-colors",
                          activeRegionId === text.region_id
                            ? "border-[#F4B287] bg-orange-50/50"
                            : "border-transparent hover:border-gray-200",
                        )}
                        onClick={() => {
                          setActiveRegionId(text.region_id);
                          onSelectRegion?.(text.region_id);
                        }}
                      >
                        <span className="absolute -left-1 top-1.5 block h-2 w-2 rounded-full border border-white bg-brand-gold shadow-sm opacity-0 transition-opacity group-hover:opacity-100" />
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[9px] font-black text-[#B16A4F] uppercase tracking-tighter">
                            {orderLabel || "..."}
                          </span>
                        </div>
                        <p className="mt-1 max-w-full whitespace-pre-wrap break-words text-[12px] leading-relaxed text-brand-text [overflow-wrap:anywhere]">
                          {content || <span className="italic text-gray-300">Empty block</span>}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
