import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RightSidebar, { type OcrSidebarItem } from "../RightSidebar";
import type { PageText } from "../../../types/api";

function makeText(overrides: Partial<PageText>): PageText {
  return {
    id: "text-id",
    region_id: "region-id",
    pipeline_run_id: null,
    ocr_text_raw: "raw",
    ocr_text_corrected: null,
    ocr_confidence: null,
    context_notes: null,
    translation_draft: null,
    translation_corrected: null,
    display_text_final: null,
    render_scale: null,
    render_color: null,
    render_font_family: null,
    translation_status: "draft",
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("RightSidebar", () => {
  it("renders ordered OCR items with reading-order labels", () => {
    const items: OcrSidebarItem[] = [
      {
        text: makeText({ id: "text-a", region_id: "region-a", ocr_text_raw: "A" }),
        title: "01 · OCR Block",
        orderLabel: "P1-1",
      },
      {
        text: makeText({ id: "text-b", region_id: "region-b", ocr_text_raw: "B" }),
        title: "02 · OCR Block",
        orderLabel: "U-2",
      },
    ];

    render(
      <RightSidebar
        items={items}
        onTextChange={() => undefined}
        viewMode="Original"
        saveState="idle"
      />,
    );

    expect(screen.getByText("P1-1")).toBeInTheDocument();
    expect(screen.getByText("U-2")).toBeInTheDocument();
    expect(screen.getByText("2 blocks loaded")).toBeInTheDocument();
  });

  it("syncs selection back to region id when an OCR row is clicked", () => {
    const onSelectRegion = vi.fn();
    const items: OcrSidebarItem[] = [
      {
        text: makeText({ id: "text-a", region_id: "region-a", ocr_text_raw: "A" }),
        title: "01 · OCR Block",
        orderLabel: "P1-1",
      },
    ];

    render(
      <RightSidebar
        items={items}
        onTextChange={() => undefined}
        viewMode="Original"
        onSelectRegion={onSelectRegion}
        selectedRegionId={null}
        saveState="idle"
      />,
    );

    fireEvent.click(screen.getAllByRole("button")[0]!);
    expect(onSelectRegion).toHaveBeenCalledWith("region-a");
  });

  it("navigates OCR blocks with keyboard arrows while typing", () => {
    const onSelectRegion = vi.fn();
    const items: OcrSidebarItem[] = [
      {
        text: makeText({ id: "text-a", region_id: "region-a", ocr_text_raw: "A" }),
        title: "01 · OCR Block",
        orderLabel: "P1-1",
      },
      {
        text: makeText({ id: "text-b", region_id: "region-b", ocr_text_raw: "B" }),
        title: "02 · OCR Block",
        orderLabel: "P1-2",
      },
    ];

    render(
      <RightSidebar
        items={items}
        onTextChange={() => undefined}
        viewMode="Original"
        onSelectRegion={onSelectRegion}
        selectedRegionId="region-a"
        saveState="idle"
      />,
    );

    fireEvent.keyDown(screen.getByLabelText("01 · OCR Block"), { key: "ArrowDown" });
    expect(onSelectRegion).toHaveBeenCalledWith("region-b");

    fireEvent.keyDown(screen.getByLabelText("02 · OCR Block"), { key: "ArrowUp" });
    expect(onSelectRegion).toHaveBeenCalledWith("region-a");
  });
});
