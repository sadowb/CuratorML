import { describe, expect, it } from "vitest";

import { buildOrderedOcrItems } from "../ocrOrdering";
import type { PageRegion, PageText } from "../../types/api";

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

function makeRegion(overrides: Partial<PageRegion>): PageRegion {
  return {
    id: "region-id",
    page_id: "page-id",
    parent_region_id: null,
    pipeline_run_id: null,
    created_by_user_id: null,
    region_kind: "text",
    polygon_json: null,
    bbox_json: [0, 0, 10, 10],
    confidence: 0.9,
    reading_order: null,
    origin: "mask_inference",
    is_active: true,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("buildOrderedOcrItems", () => {
  it("sorts OCR items by panel order then item order", () => {
    const texts = [
      makeText({ id: "text-b", region_id: "text-region-b" }),
      makeText({ id: "text-a", region_id: "text-region-a" }),
    ];
    const regions = [
      makeRegion({ id: "panel-2", region_kind: "panel", reading_order: 2 }),
      makeRegion({ id: "panel-1", region_kind: "panel", reading_order: 1 }),
      makeRegion({
        id: "text-region-b",
        region_kind: "text",
        parent_region_id: "panel-2",
        reading_order: 1,
      }),
      makeRegion({
        id: "text-region-a",
        region_kind: "text",
        parent_region_id: "panel-1",
        reading_order: 1,
      }),
    ];

    const items = buildOrderedOcrItems(texts, regions, "RTL");

    expect(items.map((item) => item.text.id)).toEqual(["text-a", "text-b"]);
    expect(items.map((item) => item.orderLabel)).toEqual(["P1-1", "P2-1"]);
  });

  it("uses unparented labels for text regions without panel links", () => {
    const texts = [makeText({ id: "text-a", region_id: "text-region-a" })];
    const regions = [
      makeRegion({
        id: "text-region-a",
        region_kind: "text",
        parent_region_id: null,
        reading_order: 3,
      }),
    ];

    const items = buildOrderedOcrItems(texts, regions, "RTL");
    expect(items[0]?.orderLabel).toBe("U-3");
  });

  it("uses visual geometry before container order inside a panel", () => {
    const texts = [
      makeText({ id: "text-in-bubble", region_id: "text-region-bubble" }),
      makeText({ id: "text-direct", region_id: "text-region-direct" }),
    ];

    const regions = [
      makeRegion({ id: "panel-7", region_kind: "panel", reading_order: 7 }),
      makeRegion({
        id: "balloon-1",
        region_kind: "balloon",
        parent_region_id: "panel-7",
        reading_order: 1,
        bbox_json: [20, 80, 60, 120],
      }),
      makeRegion({
        id: "text-region-bubble",
        region_kind: "text",
        parent_region_id: "balloon-1",
        reading_order: 3,
        bbox_json: [25, 85, 55, 115],
      }),
      makeRegion({
        id: "text-region-direct",
        region_kind: "text",
        parent_region_id: "panel-7",
        reading_order: 2,
        bbox_json: [80, 20, 110, 50],
      }),
    ];

    const items = buildOrderedOcrItems(texts, regions, "RTL");
    expect(items.map((item) => item.text.id)).toEqual([
      "text-direct",
      "text-in-bubble",
    ]);
  });

  it("keeps multiple texts in the same bubble ordered by geometry when reading_order ties", () => {
    const texts = [
      makeText({ id: "text-low", region_id: "text-region-low" }),
      makeText({ id: "text-high", region_id: "text-region-high" }),
    ];

    const regions = [
      makeRegion({ id: "panel-6", region_kind: "panel", reading_order: 6 }),
      makeRegion({
        id: "balloon-3",
        region_kind: "balloon",
        parent_region_id: "panel-6",
        reading_order: 3,
      }),
      makeRegion({
        id: "text-region-low",
        region_kind: "text",
        parent_region_id: "balloon-3",
        reading_order: null,
        bbox_json: [10, 80, 40, 110],
      }),
      makeRegion({
        id: "text-region-high",
        region_kind: "text",
        parent_region_id: "balloon-3",
        reading_order: null,
        bbox_json: [10, 10, 40, 40],
      }),
    ];

    const items = buildOrderedOcrItems(texts, regions);
    expect(items.map((item) => item.text.id)).toEqual([
      "text-high",
      "text-low",
    ]);
  });

  it("orders floating text and balloon groups by container order inside the same panel", () => {
    const texts = [
      makeText({ id: "text-floating", region_id: "text-region-floating" }),
      makeText({ id: "text-bubble-1", region_id: "text-region-bubble-1" }),
      makeText({ id: "text-bubble-2", region_id: "text-region-bubble-2" }),
    ];

    const regions = [
      makeRegion({ id: "panel-3", region_kind: "panel", reading_order: 3 }),
      makeRegion({
        id: "balloon-2",
        region_kind: "balloon",
        parent_region_id: "panel-3",
        reading_order: 2,
        bbox_json: [70, 70, 100, 130],
      }),
      makeRegion({
        id: "text-region-floating",
        region_kind: "text",
        parent_region_id: "panel-3",
        reading_order: 1,
        bbox_json: [10, 20, 40, 60],
      }),
      makeRegion({
        id: "text-region-bubble-1",
        region_kind: "text",
        parent_region_id: "balloon-2",
        reading_order: 1,
        bbox_json: [70, 10, 90, 30],
      }),
      makeRegion({
        id: "text-region-bubble-2",
        region_kind: "text",
        parent_region_id: "balloon-2",
        reading_order: 2,
        bbox_json: [70, 40, 90, 60],
      }),
    ];

    const items = buildOrderedOcrItems(texts, regions);
    expect(items.map((item) => item.text.id)).toEqual([
      "text-floating",
      "text-bubble-1",
      "text-bubble-2",
    ]);
  });

  it("uses right-to-left geometric tie-breaks in RTL reading mode", () => {
    const texts = [
      makeText({ id: "text-left", region_id: "text-region-left" }),
      makeText({ id: "text-right", region_id: "text-region-right" }),
    ];

    const regions = [
      makeRegion({ id: "panel-1", region_kind: "panel", reading_order: 1 }),
      makeRegion({
        id: "text-region-left",
        region_kind: "text",
        parent_region_id: "panel-1",
        reading_order: null,
        bbox_json: [20, 20, 40, 40],
      }),
      makeRegion({
        id: "text-region-right",
        region_kind: "text",
        parent_region_id: "panel-1",
        reading_order: null,
        bbox_json: [80, 20, 100, 40],
      }),
    ];

    const items = buildOrderedOcrItems(texts, regions, "RTL");
    expect(items.map((item) => item.text.id)).toEqual([
      "text-right",
      "text-left",
    ]);
  });
});
