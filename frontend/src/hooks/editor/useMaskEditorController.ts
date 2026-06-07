import { useEffect, useMemo } from "react";
import type { PageRegion } from "../../types/api";
import type { InpaintOptionsPayload } from "../../types/api";
import type { MaskEditorController } from "./maskEditorTypes";
import { useMaskStore } from "./useMaskStore";
import { useMaskPersistence } from "./useMaskPersistence";

interface UseMaskEditorControllerParams {
  pageId?: string;
  targetLanguage?: string;
  translationEnableThinking?: boolean;
  inpaintOptions: InpaintOptionsPayload;
  regions: PageRegion[];
  refreshPageDetail: (targetPageId: string) => Promise<unknown>;
}

/**
 * Unified mask editor controller (Orchestrator).
 * Refactored from 600+ lines to ~80 lines.
 */
export function useMaskEditorController({
  pageId,
  targetLanguage,
  translationEnableThinking = true,
  inpaintOptions,
  regions,
  refreshPageDetail,
}: UseMaskEditorControllerParams): MaskEditorController {
  
  const store = useMaskStore(regions, pageId);
  const persistence = useMaskPersistence(
    pageId, 
    targetLanguage, 
    translationEnableThinking,
    inpaintOptions,
    refreshPageDetail, 
    store.actions, 
    store.state
  );

  // -- Reset/Sync effects --------------------------------------------------
  
  // Page change reset
  useEffect(() => {
    store.actions.reset();
  }, [pageId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-show masks when they appear
  useEffect(() => {
    if (store.state.editableRegions.length > 0) {
      store.actions.setShowMasks(true);
    } else {
      store.actions.setShowMasks(false);
      store.actions.setActiveMaskId(null);
      store.actions.setFilter({ mode: "all" });
    }
  }, [store.state.editableRegions.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear stale active mask
  useEffect(() => {
    if (store.state.activeMaskId && !store.state.editableRegions.some((r) => r.id === store.state.activeMaskId)) {
      store.actions.setActiveMaskId(null);
    }
  }, [store.state.activeMaskId, store.state.editableRegions]); // eslint-disable-line react-hooks/exhaustive-deps

  // -- Derived -------------------------------------------------------------
  const dirtyRegionIds = useMemo(
    () => Array.from(new Set([...store.state.dirtyIds, ...store.state.deletedIds])),
    [store.state.dirtyIds, store.state.deletedIds],
  );

  // -- Return --------------------------------------------------------------
  return {
    workflow: {
      dirtyRegionIds,
      hasDirtyMasks: dirtyRegionIds.length > 0,
      isRunningMaskInference: persistence.state.isRunningInference,
      isRunningOCR: persistence.state.isRunningOCR,
      isRuningInpaint: persistence.state.isRuningInpaint,
      isRunningTranslate: persistence.state.isRunningTranslate,
      isSavingMasks: persistence.state.isSavingMasks,
      jobPhase: persistence.state.jobPhase,
      jobDetail: persistence.state.jobDetail,
      runMaskInference: persistence.actions.runMaskInference,
      runOCR: persistence.actions.runOCR,
      runInpaint: persistence.actions.runInpaint,
      runTranslate: persistence.actions.runTranslate,
      saveMasks: persistence.actions.saveMasks,
    },
    workspace: {
      pageId,
      ...store.state,
      maskError: persistence.state.maskError,
      regions: store.state.filteredRegions,
      allRegions: store.state.maskRegions,
      toggleShowMasks: () => store.actions.setShowMasks(!store.state.showMasks),
      toggleShowLabels: () => store.actions.setShowLabels(!store.state.showLabels),
      setFilterAll: () => store.actions.setFilter({ mode: "all" }),
      setFilterByKind: (kind: string) => store.actions.setFilter(!kind || kind === "all" ? { mode: "all" } : { mode: "kind", regionKind: kind }),
      onRegionPolygonChange: store.actions.handleRegionPolygonChange,
      onRegionDelete: store.actions.handleRegionDelete,
      onRegionCreate: store.actions.handleRegionCreate,
      setTextStyle: store.actions.handleSetTextStyle,
      setActiveTool: store.actions.setActiveTool,
      setActiveMaskId: store.actions.setActiveMaskId,
      setPenShape: store.actions.setPenShape,
      setPenTarget: store.actions.setPenTarget,
    },
  };
}
