import { cn } from "../../lib/utils";

interface OCRBlockProps {
  title: string;
  orderLabel?: string;
  sourceText?: string | null;
  sourceLabel?: string;
  value: string;
  onChange: (value: string) => void;
  onSelect?: () => void;
  active?: boolean;
  className?: string;
  textScale?: number;
  onTextScaleChange?: (nextScale: number) => void;
  onNavigatePrevious?: () => void;
  onNavigateNext?: () => void;
  inputRef?: (node: HTMLInputElement | null) => void;
}

export default function OCRBlock({
  title,
  orderLabel,
  sourceText,
  sourceLabel = "Raw",
  value,
  onChange,
  onSelect,
  active = false,
  className,
  textScale = 1,
  onTextScaleChange,
  onNavigatePrevious,
  onNavigateNext,
  inputRef,
}: OCRBlockProps) {
  const isInteractiveTarget = (target: EventTarget | null): boolean => {
    if (!(target instanceof HTMLElement)) return false;
    return Boolean(target.closest("input, textarea, select, button, a"));
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={(event) => {
        if (isInteractiveTarget(event.target)) return;
        onSelect?.();
      }}
      onKeyDown={(event) => {
        if (isInteractiveTarget(event.target)) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect?.();
        }
      }}
      className={cn(
        "flex flex-col gap-2.5 rounded-[10px] border border-[#F1DDD0] bg-[#FFF8F2] p-3 shadow-[0_4px_12px_rgba(0,0,0,0.03)] outline-none transition-all",
        active &&
          "border-[#F4B287] bg-[#FFF4E8] shadow-[0_6px_16px_rgba(177,106,79,0.16)]",
        onSelect &&
          "cursor-pointer focus-visible:ring-2 focus-visible:ring-[#F4B287] focus-visible:ring-offset-1",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-caption text-[10.5px] font-bold uppercase tracking-[0.05em] text-[#B16A4F]">
          {title}
        </div>
        {orderLabel ? (
          <span className="rounded-full border border-[#E9D7C7] bg-[#FFF8F1] px-2 py-0.5 font-caption text-[9px] font-bold text-brand-text-muted">
            {orderLabel}
          </span>
        ) : null}
      </div>
      {sourceText ? (
        <div className="max-w-full whitespace-pre-wrap break-words text-[10px] leading-relaxed text-brand-text-muted [overflow-wrap:anywhere]">
          {sourceLabel}: {sourceText}
        </div>
      ) : null}
      <input
        type="text"
        ref={inputRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onFocus={onSelect}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            onNavigateNext?.();
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            onNavigatePrevious?.();
          }
        }}
        aria-label={title}
        className="h-8 w-full rounded-[8px] border border-[#E8DED0] bg-white px-3 text-[11px] font-medium text-brand-text focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-gold"
      />
      {onTextScaleChange ? (
        <div
          className="mt-1 flex items-center gap-2"
          onPointerDown={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.stopPropagation()}
          onTouchStart={(event) => event.stopPropagation()}
        >
          <span className="text-[10px] font-semibold text-brand-text-muted">
            Size
          </span>
          <input
            type="range"
            min={0.6}
            max={2}
            step={0.05}
            value={textScale}
            onChange={(event) => onTextScaleChange(Number(event.target.value))}
            onInput={(event) =>
              onTextScaleChange(Number((event.target as HTMLInputElement).value))
            }
            onClick={(event) => event.stopPropagation()}
            onPointerDown={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
            onTouchStart={(event) => event.stopPropagation()}
            className="h-1 w-full accent-[#F4B287]"
            aria-label={`${title} size`}
          />
          <span className="w-10 text-right text-[10px] font-semibold text-brand-text-muted">
            {Math.round(textScale * 100)}%
          </span>
        </div>
      ) : null}
    </div>
  );
}
