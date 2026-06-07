import type { KeyboardEvent } from "react";
import { cn } from "../../lib/utils";

interface PageOption {
  id: string;
  page_number: number;
  thumbnail_url?: string | null;
}

interface BottomBarProps {
  pages: PageOption[];
  currentPageId?: string;
  onPageSelect: (pageId: string) => void;
}

function ArrowGlyph({ direction }: { direction: "left" | "right" }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex h-5 w-5 items-center justify-center text-[14px] leading-none text-[#111111]"
    >
      {direction === "left" ? "‹" : "›"}
    </span>
  );
}

export default function BottomBar({
  pages,
  currentPageId,
  onPageSelect,
}: BottomBarProps) {
  const currentIndex = pages.findIndex((page) => page.id === currentPageId);
  const safeIndex = currentIndex >= 0 ? currentIndex : 0;

  const previousPage = safeIndex > 0 ? pages[safeIndex - 1] : undefined;
  const nextPage = safeIndex < pages.length - 1 ? pages[safeIndex + 1] : undefined;

  const visibleWindow = 5;
  let start = Math.max(0, safeIndex - Math.floor(visibleWindow / 2));
  const end = Math.min(pages.length, start + visibleWindow);
  if (end - start < visibleWindow) start = Math.max(0, end - visibleWindow);
  const visiblePages = pages.slice(start, end);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowLeft" && previousPage) {
      event.preventDefault();
      onPageSelect(previousPage.id);
      return;
    }

    if (event.key === "ArrowRight" && nextPage) {
      event.preventDefault();
      onPageSelect(nextPage.id);
    }
  };

  const navButtonClass =
    "flex h-[30px] items-center justify-center gap-[6px] rounded-md border border-[#D8C9B8] bg-[#FBF7F1] px-3 font-sans text-[11px] font-medium text-[#241B17] shadow-[0_4px_12px_rgba(42,28,19,0.04)] transition-colors hover:bg-white disabled:opacity-30";

  return (
    <div
      className="z-20 flex h-[64px] w-full shrink-0 flex-none border-t border-[#F1DDD0] bg-[#FFFDFB] px-6 py-[8px]"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      aria-label="Compact page navigator"
    >
      <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div />

        <div className="flex w-fit max-w-full items-center gap-[10px] overflow-x-auto scrollbar-hide rounded-[12px] border border-[#F1DDD0] bg-white px-2.5 py-[6px] shadow-[0_8px_20px_rgba(0,0,0,0.05)]">
          <button
            className={navButtonClass}
            onClick={() => previousPage && onPageSelect(previousPage.id)}
            disabled={!previousPage}
          >
            <ArrowGlyph direction="left" />
            Prev
          </button>

          <div className="flex shrink-0 items-center gap-[10px]">
            {visiblePages.map((page) => {
              const isCurrent = page.id === currentPageId;

              return (
                <button
                  key={page.id}
                  onClick={() => onPageSelect(page.id)}
                  className={cn(
                    "relative h-[42px] w-[34px] shrink-0 rounded-[8px] bg-white p-0",
                    isCurrent
                      ? "border-2 border-[#7D6B3D] shadow-[0_4px_12px_rgba(42,28,19,0.08)]"
                      : "border border-[#D8C9B8]",
                  )}
                >
                  <div className="flex h-full w-full items-end justify-center overflow-hidden rounded-[5px] bg-zinc-50 p-[3px]">
                    {page.thumbnail_url ? (
                      <img
                        src={page.thumbnail_url}
                        alt={`Page ${page.page_number}`}
                        className="h-full w-full object-contain"
                        loading="lazy"
                      />
                    ) : (
                      <span className="text-[8px] font-medium text-zinc-400">--</span>
                    )}
                  </div>
                  <span className="absolute left-1 top-0.5 text-[8px] font-semibold text-white [text-shadow:0_1px_3px_rgba(0,0,0,0.55)]">
                    {page.page_number}
                  </span>
                </button>
              );
            })}
          </div>

          <button
            className={navButtonClass}
            onClick={() => nextPage && onPageSelect(nextPage.id)}
            disabled={!nextPage}
          >
            Next
            <ArrowGlyph direction="right" />
          </button>
        </div>

        <div className="flex justify-end">
          <div className="rounded-full border border-[#F1DDD0] bg-[#FFF8F2] px-[10px] py-[5px] shadow-[0_4px_10px_rgba(42,28,19,0.04)]">
            <span className="font-caption text-[10px] font-semibold text-[#666666]">
              Page {pages.length === 0 ? "0/0" : `${safeIndex + 1}/${pages.length}`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
