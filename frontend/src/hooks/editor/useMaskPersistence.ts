import { useState, useCallback, useEffect, useRef } from "react";
import { patchPageRegion, createPageRegion } from "../../lib/api/pages";
import { submitJob } from "../../lib/api/jobs";
import type { InpaintOptionsPayload, PageRegion, TranslateOptionsPayload } from "../../types/api";
import { useEditorStore, type PipelineStage } from "../../store/useEditorStore";
import type { useMaskStore } from "./useMaskStore";
import { useJobStatus } from "./useJobStatus";
import { deriveBbox, isEditablePolygon } from "./utils/maskGeometry";

type JobOptions = InpaintOptionsPayload | TranslateOptionsPayload;
type MaskStore = ReturnType<typeof useMaskStore>;
type PersistedPipelineStage = "mask_inference" | "ocr" | "translate";

const PERSISTED_JOB_STAGES: PersistedPipelineStage[] = [
  "mask_inference",
  "ocr",
  "translate",
];

function hasStringId(value: unknown): value is { id: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof (value as { id: unknown }).id === "string"
  );
}

function remapRecordKeys<T>(
  prev: Record<string, T>,
  idMapping: Record<string, string>,
): Record<string, T> {
  const next = { ...prev };
  Object.entries(idMapping).forEach(([tempId, realId]) => {
    if (next[tempId] !== undefined) {
      next[realId] = next[tempId];
      delete next[tempId];
    }
  });
  return next;
}

function isPersistedJobStage(stage: PipelineStage): stage is PersistedPipelineStage {
  return PERSISTED_JOB_STAGES.includes(stage as PersistedPipelineStage);
}

export function useMaskPersistence(
  pageId: string | undefined,
  targetLanguage: string | undefined,
  translationEnableThinking: boolean,
  inpaintOptions: InpaintOptionsPayload,
  refreshPageDetail: (id: string) => Promise<unknown>,
  storeActions: MaskStore["actions"],
  storeState: MaskStore["state"],
) {
  const [isRunningInference, setIsRunningInference] = useState(false);
  const [isRunningOCR, setIsRunningOCR] = useState(false);
  const [isRunningInpaint, setIsRunningInpaint] = useState(false);
  const [isRunningTranslate, setIsRunningTranslate] = useState(false);
  const [isSavingMasks, setIsSavingMasks] = useState(false);
  const [maskError, setMaskError] = useState<string | null>(null);
  const trackedJobRef = useRef<{ pageId: string; stage: PipelineStage } | null>(null);

  const setActivePipelineJob = useEditorStore((state) => state.setActivePipelineJob);
  const clearActivePipelineJob = useEditorStore((state) => state.clearActivePipelineJob);
  const getActivePipelineJob = useEditorStore((state) => state.getActivePipelineJob);

  const setRunningForStage = useCallback((stage: PipelineStage, running: boolean) => {
    const setters: Partial<Record<PipelineStage, (value: boolean) => void>> = {
      mask_inference: setIsRunningInference,
      ocr: setIsRunningOCR,
      inpaint: setIsRunningInpaint,
      translate: setIsRunningTranslate,
    };

    setters[stage]?.(running);
  }, []);

  const {
    phase: jobPhase,
    detail: jobDetail,
    trackJob,
    reset: resetJobStatus,
  } = useJobStatus({
    onCompleted: () => {
      const trackedJob = trackedJobRef.current;
      if (trackedJob) {
        clearActivePipelineJob(trackedJob.pageId, trackedJob.stage);
        void refreshPageDetail(trackedJob.pageId);
      }
      setIsRunningInference(false);
      setIsRunningOCR(false);
      setIsRunningInpaint(false);
      setIsRunningTranslate(false);
      trackedJobRef.current = null;
    },
    onFailed: (error) => {
      const trackedJob = trackedJobRef.current;
      if (trackedJob) {
        clearActivePipelineJob(trackedJob.pageId, trackedJob.stage);
      }
      setMaskError(error);
      setIsRunningInference(false);
      setIsRunningOCR(false);
      setIsRunningInpaint(false);
      setIsRunningTranslate(false);
      trackedJobRef.current = null;
    },
  });

  useEffect(() => {
    setIsRunningInference(false);
    setIsRunningOCR(false);
    setIsRunningInpaint(false);
    setIsRunningTranslate(false);
    setMaskError(null);

    if (!pageId) {
      trackedJobRef.current = null;
      resetJobStatus();
      return;
    }

    const activeJob = PERSISTED_JOB_STAGES
      .map((stage) => getActivePipelineJob(pageId, stage))
      .filter((job) => job !== null)
      .sort((a, b) => b.createdAt - a.createdAt)[0];

    if (!activeJob) {
      trackedJobRef.current = null;
      resetJobStatus();
      return;
    }

    trackedJobRef.current = { pageId, stage: activeJob.stage };
    setRunningForStage(activeJob.stage, true);
    trackJob(activeJob.jobId);
  }, [pageId, getActivePipelineJob, resetJobStatus, setRunningForStage, trackJob]);

  const runJob = useCallback(async (type: PipelineStage, options?: JobOptions, force = false) => {
    if (!pageId) return;
    setRunningForStage(type, true);
    setMaskError(null);
    try {
      const { job_id } = await submitJob(pageId, type, options, force);
      trackedJobRef.current = { pageId, stage: type };
      if (isPersistedJobStage(type)) {
        setActivePipelineJob(pageId, type, job_id);
      }
      trackJob(job_id);
    } catch (err) {
      setMaskError(err instanceof Error ? err.message : `Failed to submit ${type}`);
      setRunningForStage(type, false);
    }
  }, [pageId, setActivePipelineJob, setRunningForStage, trackJob]);

  const saveMasks = useCallback(async () => {
    const { dirtyIds, deletedIds, editableRegions, editablePolygonsByRegionId } = storeState;
    const { setDirtyIds, setDeletedIds, setCreatedRegions, setEditablePolygons, setTextStyles } = storeActions;
    
    const allDirty = Array.from(new Set([...dirtyIds, ...deletedIds]));
    if (!pageId || isSavingMasks || allDirty.length === 0) return;

    setIsSavingMasks(true);
    setMaskError(null);

    try {
      const results = await Promise.allSettled(
        allDirty.map(async (regionId) => {
          const region = editableRegions.find((item: PageRegion) => item.id === regionId);
          if (deletedIds.has(regionId)) {
            if (regionId.startsWith("temp-")) return { id: regionId, deleted: true };
            return patchPageRegion(pageId, regionId, { is_active: false });
          }

          const polygon = editablePolygonsByRegionId[regionId];
          if (!isEditablePolygon(polygon)) throw new Error("Invalid polygon");
          const bbox = deriveBbox(polygon);

          if (regionId.startsWith("temp-")) {
            return createPageRegion(pageId, {
              region_kind: region?.region_kind || "balloon",
              polygon_json: polygon,
              bbox_json: bbox,
              confidence: 1.0,
            });
          }
          return patchPageRegion(pageId, regionId, { polygon_json: polygon, bbox_json: bbox });
        }),
      );

      const failedIds: string[] = [];
      const idMapping: Record<string, string> = {};

      results.forEach((result, i) => {
        const originalId = allDirty[i];
        if (result.status === "rejected") {
          failedIds.push(originalId);
        } else {
          if (hasStringId(result.value) && originalId.startsWith("temp-")) {
            idMapping[originalId] = result.value.id;
          }
        }
      });

      if (Object.keys(idMapping).length > 0) {
        setCreatedRegions((prev: PageRegion[]) => prev.map(r => idMapping[r.id] ? { ...r, id: idMapping[r.id] } : r));
        setEditablePolygons((prev) => remapRecordKeys(prev, idMapping));
        setTextStyles((prev) => remapRecordKeys(prev, idMapping));
      }

      if (failedIds.length > 0) {
        setDirtyIds(new Set(failedIds.filter(id => !deletedIds.has(id))));
        setDeletedIds(new Set(failedIds.filter(id => deletedIds.has(id))));
        setMaskError(`Failed to save ${failedIds.length} masks.`);
      } else {
        await refreshPageDetail(pageId);
        setDirtyIds(new Set());
        setDeletedIds(new Set());
        setCreatedRegions([]);
      }
    } catch (err) {
      setMaskError(err instanceof Error ? err.message : "Failed to save masks");
    } finally {
      setIsSavingMasks(false);
    }
  }, [pageId, isSavingMasks, storeState, storeActions, refreshPageDetail]);

  return {
    state: {
      isRunningInference,
      isRunningOCR,
      isRuningInpaint: isRunningInpaint,
      isRunningTranslate,
      isSavingMasks,
      maskError,
      jobPhase,
      jobDetail,
    },
    actions: {
      runMaskInference: () => runJob("mask_inference"),
      runOCR: () => runJob("ocr"),
      runInpaint: () => runJob("inpaint", inpaintOptions),
      runTranslate: () => runJob("translate", {
        target_language: targetLanguage || "en",
        enable_thinking: translationEnableThinking,
        force_overwrite_draft: true,
        retry_missing_only: false,
      }, !!maskError),
      saveMasks,
      reset: () => {
        setIsRunningInference(false);
        setIsRunningOCR(false);
        setIsRunningInpaint(false);
        setIsRunningTranslate(false);
        setMaskError(null);
        trackedJobRef.current = null;
        resetJobStatus();
      },
    },
  };
}
