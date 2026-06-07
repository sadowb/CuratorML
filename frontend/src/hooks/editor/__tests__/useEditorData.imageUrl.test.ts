import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useEditorData } from "../useEditorData";

vi.mock("../../../lib/api", () => ({
  getPage: vi.fn(),
  getProject: vi.fn(),
  listAllChapterPages: vi.fn(),
  toAbsoluteApiUrl: vi.fn((url: string) => url),
}));

import { getPage, getProject, listAllChapterPages } from "../../../lib/api";

function makePage(overrides: Record<string, unknown> = {}) {
  return {
    id: "page-1",
    chapter_id: "ch-1",
    page_number: 1,
    current_stage: "done",
    review_status: "pending",
    created_at: "",
    updated_at: "",
    original_file_url: "/api/v1/storage/proj/ch/page-1/original",
    files: [],
    texts: [],
    regions: [],
    ...overrides,
  };
}

function makeProject() {
  return {
    project: {
      id: "proj-1",
      target_language: "en",
      reading_direction: "LTR",
    },
    chapters: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getProject).mockResolvedValue(makeProject() as never);
  vi.mocked(listAllChapterPages).mockResolvedValue([]);
});

describe("useEditorData — image URL is same-origin (no toAbsoluteApiUrl conversion)", () => {
  it("imageUrl is set to relative path — no http:// origin prefix", async () => {
    const relativeUrl = "/api/v1/storage/proj/ch/page-1/original";
    vi.mocked(getPage).mockResolvedValue(makePage({ original_file_url: relativeUrl }) as never);

    const { result } = renderHook(() =>
      useEditorData({
        projectId: "proj-1",
        pageId: "page-1",
        getPageDrafts: () => ({}),
      }),
    );

    await waitFor(() => expect(result.current.imageUrl).not.toBe(""));

    expect(result.current.imageUrl).toBe(relativeUrl);
    expect(result.current.imageUrl).not.toMatch(/^https?:\/\//);
  });

  it("imageUrl stays empty string when original_file_url is null", async () => {
    vi.mocked(getPage).mockResolvedValue(makePage({ original_file_url: null }) as never);

    const { result } = renderHook(() =>
      useEditorData({
        projectId: "proj-1",
        pageId: "page-1",
        getPageDrafts: () => ({}),
      }),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.imageUrl).toBe("");
  });

  it("inpaintedImageUrl is relative with cache-buster appended", async () => {
    const inpaintUrl = "/api/v1/storage/proj/ch/page-1/inpainted";
    const runId = "run-abc";
    vi.mocked(getPage).mockResolvedValue(
      makePage({
        files: [
          {
            id: "file-1",
            pipeline_run_id: runId,
            created_at: "2024-01-01",
            file_kind: "inpainted",
            is_current: true,
            url: inpaintUrl,
          },
        ],
      }) as never,
    );

    const { result } = renderHook(() =>
      useEditorData({
        projectId: "proj-1",
        pageId: "page-1",
        getPageDrafts: () => ({}),
      }),
    );

    await waitFor(() => expect(result.current.inpaintedImageUrl).not.toBe(""));

    expect(result.current.inpaintedImageUrl).toMatch(/^\/api\/v1\/storage\//);
    expect(result.current.inpaintedImageUrl).not.toMatch(/^https?:\/\//);
    expect(result.current.inpaintedImageUrl).toContain(`?v=${encodeURIComponent(runId)}`);
  });

  it("inpaintedImageUrl is empty when no current inpainted file exists", async () => {
    vi.mocked(getPage).mockResolvedValue(
      makePage({
        files: [
          {
            id: "file-2",
            pipeline_run_id: null,
            created_at: "2024-01-01",
            file_kind: "original",
            is_current: true,
            url: "/api/v1/storage/proj/ch/page-1/original",
          },
        ],
      }) as never,
    );

    const { result } = renderHook(() =>
      useEditorData({
        projectId: "proj-1",
        pageId: "page-1",
        getPageDrafts: () => ({}),
      }),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.inpaintedImageUrl).toBe("");
  });
});
