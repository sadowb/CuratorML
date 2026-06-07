import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PageTextPatchPayload } from "../types/api";

interface EditorDraft extends PageTextPatchPayload {
  updatedAt: number;
}

interface TextOffset {
  x: number;
  y: number;
}

interface TextBoxSize {
  width: number;
  height: number;
}

export interface InpaintSettings {
  method: "telea" | "ns";
  radius: number;
  ai_expand_strength: number;
  text_expand_px: number;
  balloon_safe_inset_mode: "auto" | "manual";
  balloon_safe_inset_px: number;
  clip_fallback_mode: "no_clip" | "inset_bbox";
}

export interface TranslationSettings {
  enable_thinking: boolean;
}

export type PipelineStage =
  | "mask_inference"
  | "ocr"
  | "inpaint"
  | "reading_order"
  | "translate"
  | "render_preview";

export interface ActivePipelineJob {
  jobId: string;
  pageId: string;
  stage: PipelineStage;
  createdAt: number;
}

interface EditorState {
  viewMode: "Original" | "Translated";
  setViewMode: (mode: "Original" | "Translated") => void;

  activeWorkflow: string;
  setActiveWorkflow: (workflow: string) => void;

  draftsByPage: Record<string, Record<string, EditorDraft>>;
  upsertDraft: (
    pageId: string,
    textId: string,
    draft: PageTextPatchPayload,
  ) => void;
  clearDraft: (pageId: string, textId: string) => void;
  getPageDrafts: (pageId: string) => Record<string, EditorDraft>;

  textScaleByPage: Record<string, Record<string, number>>;
  setTextScale: (pageId: string, textId: string, scale: number) => void;
  getPageTextScales: (pageId: string) => Record<string, number>;

  textPlacementModeByPage: Record<string, Record<string, "auto" | "manual">>;
  setTextPlacementMode: (
    pageId: string,
    regionId: string,
    mode: "auto" | "manual",
  ) => void;
  getPageTextPlacementModes: (
    pageId: string,
  ) => Record<string, "auto" | "manual">;

  textOffsetByPage: Record<string, Record<string, TextOffset>>;
  setTextOffset: (
    pageId: string,
    textId: string,
    offset: TextOffset,
  ) => void;
  clearTextOffset: (
    pageId: string,
    textId: string,
  ) => void;
  getPageTextOffsets: (
    pageId: string,
  ) => Record<string, TextOffset>;

  textBoxSizeByPage: Record<string, Record<string, TextBoxSize>>;
  setTextBoxSize: (
    pageId: string,
    textId: string,
    size: TextBoxSize,
  ) => void;
  clearTextBoxSize: (
    pageId: string,
    textId: string,
  ) => void;
  getPageTextBoxSizes: (
    pageId: string,
  ) => Record<string, TextBoxSize>;
  renderBoundsByPage: Record<string, Record<string, [number, number, number, number]>>;
  setRenderBounds: (
    pageId: string,
    textId: string,
    bounds: [number, number, number, number],
  ) => void;
  clearRenderBounds: (
    pageId: string,
    textId: string,
  ) => void;
  getPageRenderBounds: (
    pageId: string,
  ) => Record<string, [number, number, number, number]>;

  inpaintSettings: InpaintSettings;
  setInpaintSettings: (patch: Partial<InpaintSettings>) => void;

  translationSettings: TranslationSettings;
  setTranslationSettings: (patch: Partial<TranslationSettings>) => void;

  activePipelineJobsByPage: Record<
    string,
    Partial<Record<PipelineStage, ActivePipelineJob>>
  >;
  setActivePipelineJob: (
    pageId: string,
    stage: PipelineStage,
    jobId: string,
  ) => void;
  clearActivePipelineJob: (pageId: string, stage: PipelineStage) => void;
  getActivePipelineJob: (
    pageId: string,
    stage: PipelineStage,
  ) => ActivePipelineJob | null;
}

const DEFAULT_INPAINT_SETTINGS: InpaintSettings = {
  method: "telea",
  radius: 5,
  ai_expand_strength: 0.2,
  text_expand_px: 0,
  balloon_safe_inset_mode: "auto",
  balloon_safe_inset_px: 4,
  clip_fallback_mode: "no_clip",
};

const DEFAULT_TRANSLATION_SETTINGS: TranslationSettings = {
  enable_thinking: true,
};

export const useEditorStore = create<EditorState>()(
  persist(
    (set, get) => ({
      viewMode: "Original",
      setViewMode: (mode) => set({ viewMode: mode }),

      activeWorkflow: "Mask",
      setActiveWorkflow: (workflow) => set({ activeWorkflow: workflow }),

      draftsByPage: {},
      textScaleByPage: {},
      textPlacementModeByPage: {},
      textOffsetByPage: {},
      textBoxSizeByPage: {},
      renderBoundsByPage: {},
      inpaintSettings: DEFAULT_INPAINT_SETTINGS,
      translationSettings: DEFAULT_TRANSLATION_SETTINGS,
      activePipelineJobsByPage: {},

      upsertDraft: (pageId, textId, draft) =>
        set((state) => {
          const pageDrafts = state.draftsByPage[pageId] ?? {};
          return {
            draftsByPage: {
              ...state.draftsByPage,
              [pageId]: {
                ...pageDrafts,
                [textId]: {
                  ...(pageDrafts[textId] ?? { updatedAt: Date.now() }),
                  ...draft,
                  updatedAt: Date.now(),
                },
              },
            },
          };
        }),

      clearDraft: (pageId, textId) =>
        set((state) => {
          const pageDrafts = { ...(state.draftsByPage[pageId] ?? {}) };
          delete pageDrafts[textId];

          const nextDrafts = { ...state.draftsByPage };
          if (Object.keys(pageDrafts).length === 0) {
            delete nextDrafts[pageId];
          } else {
            nextDrafts[pageId] = pageDrafts;
          }

          return { draftsByPage: nextDrafts };
        }),

      getPageDrafts: (pageId) => get().draftsByPage[pageId] ?? {},

      setTextScale: (pageId, textId, scale) =>
        set((state) => ({
          textScaleByPage: {
            ...state.textScaleByPage,
            [pageId]: {
              ...(state.textScaleByPage[pageId] ?? {}),
              [textId]: Math.min(Math.max(scale, 0.6), 2),
            },
          },
        })),

      getPageTextScales: (pageId) => get().textScaleByPage[pageId] ?? {},

      setTextPlacementMode: (pageId, regionId, mode) =>
        set((state) => ({
          textPlacementModeByPage: {
            ...state.textPlacementModeByPage,
            [pageId]: {
              ...(state.textPlacementModeByPage[pageId] ?? {}),
              [regionId]: mode,
            },
          },
        })),

      getPageTextPlacementModes: (pageId) =>
        get().textPlacementModeByPage[pageId] ?? {},

      setTextOffset: (pageId, textId, offset) =>
        set((state) => ({
          textOffsetByPage: {
            ...state.textOffsetByPage,
            [pageId]: {
              ...(state.textOffsetByPage[pageId] ?? {}),
              [textId]: {
                x: Number.isFinite(offset.x) ? offset.x : 0,
                y: Number.isFinite(offset.y) ? offset.y : 0,
              },
            },
          },
        })),

      clearTextOffset: (pageId, textId) =>
        set((state) => {
          const pageOffsets = { ...(state.textOffsetByPage[pageId] ?? {}) };
          delete pageOffsets[textId];

          const nextOffsets = { ...state.textOffsetByPage };
          if (Object.keys(pageOffsets).length === 0) {
            delete nextOffsets[pageId];
          } else {
            nextOffsets[pageId] = pageOffsets;
          }

          return { textOffsetByPage: nextOffsets };
        }),

      getPageTextOffsets: (pageId) => get().textOffsetByPage[pageId] ?? {},

      setTextBoxSize: (pageId, textId, size) =>
        set((state) => ({
          textBoxSizeByPage: {
            ...state.textBoxSizeByPage,
            [pageId]: {
              ...(state.textBoxSizeByPage[pageId] ?? {}),
              [textId]: {
                width: Number.isFinite(size.width) ? Math.max(size.width, 24) : 24,
                height: Number.isFinite(size.height) ? Math.max(size.height, 18) : 18,
              },
            },
          },
        })),

      clearTextBoxSize: (pageId, textId) =>
        set((state) => {
          const pageSizes = { ...(state.textBoxSizeByPage[pageId] ?? {}) };
          delete pageSizes[textId];

          const nextSizes = { ...state.textBoxSizeByPage };
          if (Object.keys(pageSizes).length === 0) {
            delete nextSizes[pageId];
          } else {
            nextSizes[pageId] = pageSizes;
          }

          return { textBoxSizeByPage: nextSizes };
        }),

      getPageTextBoxSizes: (pageId) => get().textBoxSizeByPage[pageId] ?? {},

      setRenderBounds: (pageId, textId, bounds) =>
        set((state) => ({
          renderBoundsByPage: {
            ...state.renderBoundsByPage,
            [pageId]: {
              ...(state.renderBoundsByPage[pageId] ?? {}),
              [textId]: bounds,
            },
          },
        })),

      clearRenderBounds: (pageId, textId) =>
        set((state) => {
          const pageBounds = { ...(state.renderBoundsByPage[pageId] ?? {}) };
          delete pageBounds[textId];

          const nextBounds = { ...state.renderBoundsByPage };
          if (Object.keys(pageBounds).length === 0) {
            delete nextBounds[pageId];
          } else {
            nextBounds[pageId] = pageBounds;
          }

          return { renderBoundsByPage: nextBounds };
        }),

      getPageRenderBounds: (pageId) => get().renderBoundsByPage[pageId] ?? {},

      setInpaintSettings: (patch) =>
        set((state) => {
          const nextMode = patch.balloon_safe_inset_mode ?? state.inpaintSettings.balloon_safe_inset_mode;
          const next: InpaintSettings = {
            ...state.inpaintSettings,
            ...patch,
          };

          next.radius = Math.min(Math.max(Number(next.radius) || 1, 1), 20);
          next.ai_expand_strength = Math.min(Math.max(Number(next.ai_expand_strength) || 0, 0), 1);
          next.text_expand_px = Math.min(Math.max(Number(next.text_expand_px) || 0, 0), 40);
          next.balloon_safe_inset_px = Math.min(Math.max(Number(next.balloon_safe_inset_px) || 0, 0), 64);
          next.balloon_safe_inset_mode = nextMode;

          return { inpaintSettings: next };
        }),

      setTranslationSettings: (patch) =>
        set((state) => ({
          translationSettings: {
            ...state.translationSettings,
            ...patch,
          },
        })),

      setActivePipelineJob: (pageId, stage, jobId) =>
        set((state) => ({
          activePipelineJobsByPage: {
            ...state.activePipelineJobsByPage,
            [pageId]: {
              ...(state.activePipelineJobsByPage[pageId] ?? {}),
              [stage]: {
                jobId,
                pageId,
                stage,
                createdAt: Date.now(),
              },
            },
          },
        })),

      clearActivePipelineJob: (pageId, stage) =>
        set((state) => {
          const pageJobs = { ...(state.activePipelineJobsByPage[pageId] ?? {}) };
          delete pageJobs[stage];

          const nextJobs = { ...state.activePipelineJobsByPage };
          if (Object.keys(pageJobs).length === 0) {
            delete nextJobs[pageId];
          } else {
            nextJobs[pageId] = pageJobs;
          }

          return { activePipelineJobsByPage: nextJobs };
        }),

      getActivePipelineJob: (pageId, stage) =>
        get().activePipelineJobsByPage[pageId]?.[stage] ?? null,
    }),
    {
      name: "manga-editor-drafts-v1",
    },
  ),
);
