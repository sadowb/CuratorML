import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMaskEditorController } from "../useMaskEditorController";
import type { PageRegion } from "../../../types/api";
import { useEditorStore } from "../../../store/useEditorStore";
import { patchPageRegion } from "../../../lib/api/pages";
import { streamJobStatus, submitJob } from "../../../lib/api/jobs";

vi.mock("../../../lib/api/pages", () => {
  return {
    patchPageRegion: vi.fn(),
  };
});
vi.mock("../../../lib/api/jobs", () => {
  return {
    submitJob: vi.fn(),
    streamJobStatus: vi.fn(() => () => undefined),
  };
});

describe("useMaskEditorController", () => {
  const patchPageRegionMock = vi.mocked(patchPageRegion);
  const submitJobMock = vi.mocked(submitJob);
  const streamJobStatusMock = vi.mocked(streamJobStatus);

  beforeEach(() => {
    patchPageRegionMock.mockReset();
    patchPageRegionMock.mockResolvedValue({} as never);
    submitJobMock.mockReset();
    submitJobMock.mockResolvedValue({
      job_id: "job-1",
      page_id: "page-1",
      stage: "inpaint",
      status: "pending",
    } as never);
    streamJobStatusMock.mockReset();
    streamJobStatusMock.mockReturnValue(() => undefined);
    useEditorStore.setState({ activePipelineJobsByPage: {} });
  });

  it("builds editable text geometry from bbox even when polygon_json is missing", () => {
    const textRegion: PageRegion = {
      id: "text-1",
      page_id: "page-1",
      parent_region_id: null,
      pipeline_run_id: null,
      created_by_user_id: null,
      region_kind: "text",
      polygon_json: null,
      bbox_json: [10, 12, 40, 50],
      confidence: 0.9,
      reading_order: null,
      origin: "mask_inference",
      is_active: true,
      created_at: "",
      updated_at: "",
    };
    const regions = [textRegion];
    const refreshPageDetail = vi.fn().mockResolvedValue({});

    const { result } = renderHook(() =>
      useMaskEditorController({
        pageId: "page-1",
        inpaintOptions: { method: "telea", radius: 5 },
        regions,
        refreshPageDetail,
      }),
    );

    expect(result.current.workspace.regions).toHaveLength(1);
    expect(result.current.workspace.editablePolygonsByRegionId["text-1"]).toEqual([
      [10, 12],
      [40, 12],
      [40, 50],
      [10, 50],
    ]);
  });

  it("saves text and panel edits as polygon+bbox", async () => {
    const textRegion: PageRegion = {
      id: "text-1",
      page_id: "page-1",
      parent_region_id: null,
      pipeline_run_id: null,
      created_by_user_id: null,
      region_kind: "text",
      polygon_json: null,
      bbox_json: [10, 10, 30, 30],
      confidence: 0.9,
      reading_order: null,
      origin: "mask_inference",
      is_active: true,
      created_at: "",
      updated_at: "",
    };

    const panelRegion: PageRegion = {
      id: "panel-1",
      page_id: "page-1",
      parent_region_id: null,
      pipeline_run_id: null,
      created_by_user_id: null,
      region_kind: "panel",
      polygon_json: [
        [60, 60],
        [120, 60],
        [120, 120],
        [60, 120],
      ],
      bbox_json: [60, 60, 120, 120],
      confidence: 0.9,
      reading_order: null,
      origin: "mask_inference",
      is_active: true,
      created_at: "",
      updated_at: "",
    };

    const regions = [textRegion, panelRegion];
    const refreshPageDetail = vi.fn().mockResolvedValue({});

    const { result } = renderHook(() =>
      useMaskEditorController({
        pageId: "page-1",
        inpaintOptions: { method: "telea", radius: 5 },
        regions,
        refreshPageDetail,
      }),
    );

    act(() => {
      result.current.workspace.onRegionPolygonChange("text-1", [
        [12, 14],
        [42, 14],
        [42, 46],
        [12, 46],
      ]);
      result.current.workspace.onRegionPolygonChange("panel-1", [
        [65, 65],
        [125, 65],
        [125, 125],
        [65, 125],
      ]);
    });

    await act(async () => {
      await result.current.workflow.saveMasks();
    });

    expect(patchPageRegionMock).toHaveBeenCalledTimes(2);

    const textCall = patchPageRegionMock.mock.calls.find((call) => call[1] === "text-1");
    const panelCall = patchPageRegionMock.mock.calls.find((call) => call[1] === "panel-1");

    expect(textCall?.[2]).toEqual({
      polygon_json: [
        [12, 14],
        [42, 14],
        [42, 46],
        [12, 46],
      ],
      bbox_json: [12, 14, 42, 46],
    });
    expect(panelCall?.[2]).toEqual({
      polygon_json: [
        [65, 65],
        [125, 65],
        [125, 125],
        [65, 125],
      ],
      bbox_json: [65, 65, 125, 125],
    });
    expect(refreshPageDetail).toHaveBeenCalledWith("page-1");
  });

  it("submits updated inpaint options from UI state", async () => {
    const refreshPageDetail = vi.fn().mockResolvedValue({});
    const regions: PageRegion[] = [];

    const { result, rerender } = renderHook(
      ({
        options,
      }: {
        options: {
          method: "telea" | "ns";
          radius: number;
          ai_expand_strength: number;
          text_expand_px: number;
        };
      }) =>
        useMaskEditorController({
          pageId: "page-1",
          inpaintOptions: options,
          regions,
          refreshPageDetail,
        }),
      {
        initialProps: {
          options: { method: "telea", radius: 5, ai_expand_strength: 0.2, text_expand_px: 0 },
        },
      },
    );

    await act(async () => {
      await result.current.workflow.runInpaint();
    });

    expect(submitJobMock).toHaveBeenLastCalledWith(
      "page-1",
      "inpaint",
      expect.objectContaining({
        method: "telea",
        radius: 5,
        ai_expand_strength: 0.2,
        text_expand_px: 0,
      }),
      false,
    );

    rerender({
      options: { method: "ns", radius: 12, ai_expand_strength: 0.85, text_expand_px: 40 },
    });

    await act(async () => {
      await result.current.workflow.runInpaint();
    });

    expect(submitJobMock).toHaveBeenLastCalledWith(
      "page-1",
      "inpaint",
      expect.objectContaining({
        method: "ns",
        radius: 12,
        ai_expand_strength: 0.85,
        text_expand_px: 40,
      }),
      false,
    );
  });

  it.each([
    ["mask inference", "runMaskInference", "mask_inference", "isRunningMaskInference"],
    ["OCR", "runOCR", "ocr", "isRunningOCR"],
    ["translate", "runTranslate", "translate", "isRunningTranslate"],
  ] as const)(
    "reattaches to an active %s job when returning to a page",
    async (_label, action, stage, runningFlag) => {
    const refreshPageDetail = vi.fn().mockResolvedValue({});
    const regions: PageRegion[] = [];

    const { result, rerender } = renderHook(
      ({ pageId }: { pageId: string }) =>
        useMaskEditorController({
          pageId,
          targetLanguage: "en",
          inpaintOptions: { method: "telea", radius: 5 },
          regions,
          refreshPageDetail,
        }),
      {
        initialProps: { pageId: "page-1" },
      },
    );

    await act(async () => {
      await result.current.workflow[action]();
    });

    if (stage === "translate") {
      expect(submitJobMock).toHaveBeenLastCalledWith(
        "page-1",
        "translate",
        expect.objectContaining({
          target_language: "en",
          force_overwrite_draft: true,
        }),
        false,
      );
    } else {
      expect(submitJobMock).toHaveBeenLastCalledWith(
        "page-1",
        stage,
        undefined,
        false,
      );
    }

    expect(result.current.workflow[runningFlag]).toBe(true);
    expect(streamJobStatusMock).toHaveBeenLastCalledWith(
      "job-1",
      expect.any(Function),
      expect.any(Function),
    );

    await act(async () => {
      rerender({ pageId: "page-2" });
    });

    expect(result.current.workflow[runningFlag]).toBe(false);

    await act(async () => {
      rerender({ pageId: "page-1" });
    });

    expect(result.current.workflow[runningFlag]).toBe(true);
    expect(streamJobStatusMock).toHaveBeenCalledTimes(2);
    expect(streamJobStatusMock).toHaveBeenLastCalledWith(
      "job-1",
      expect.any(Function),
      expect.any(Function),
    );
    },
  );

  it.each([
    ["mask inference", "runMaskInference", "mask_inference"],
    ["OCR", "runOCR", "ocr"],
  ] as const)("refreshes the page when a %s job completes", async (_label, action, stage) => {
    const refreshPageDetail = vi.fn().mockResolvedValue({});
    const regions: PageRegion[] = [];

    const { result } = renderHook(() =>
      useMaskEditorController({
        pageId: "page-1",
        inpaintOptions: { method: "telea", radius: 5 },
        regions,
        refreshPageDetail,
      }),
    );

    await act(async () => {
      await result.current.workflow[action]();
    });

    const onJobEvent =
      streamJobStatusMock.mock.calls[streamJobStatusMock.mock.calls.length - 1]?.[1];
    expect(onJobEvent).toBeDefined();

    await act(async () => {
      onJobEvent?.({
        job_id: "job-1",
        status: "completed",
        detail: "done",
        payload: {},
      });
    });

    expect(refreshPageDetail).toHaveBeenCalledWith("page-1");
    expect(useEditorStore.getState().getActivePipelineJob("page-1", stage)).toBeNull();
  });
});
