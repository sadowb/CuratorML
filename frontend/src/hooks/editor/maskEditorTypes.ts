import type { PageRegion } from "../../types/api";

export type EditorTool = "select" | "eraser" | "pen";

export type MaskRegionFilter =
  | { mode: "all" }
  | { mode: "kind"; regionKind: string };

export interface TypographyStyle {
  color: string;
  fontFamily: string;
  fontSize: "sm" | "md" | "lg";
  fontWeight: "normal" | "bold";
  textAlign: "left" | "center" | "right";
}

export interface WorkflowMaskController {
  dirtyRegionIds: string[];
  hasDirtyMasks: boolean;
  isRunningMaskInference: boolean;
  isRunningOCR: boolean;
  isRuningInpaint: boolean;
  isRunningTranslate: boolean;
  isSavingMasks: boolean;
  /** Current phase of the background inference job. */
  jobPhase: "idle" | "submitting" | "pending" | "running" | "completed" | "failed";
  /** Human-readable detail from the SSE stream. */
  jobDetail: string | null;
  runMaskInference: () => Promise<void>;
  runInpaint: () => Promise<void>;
  runOCR: () => Promise<void>;
  runTranslate: () => Promise<void>;
  saveMasks: () => Promise<void>;
}

export interface WorkspaceMaskController {
  pageId?: string;
  activeTool: EditorTool;
  setActiveTool: (tool: EditorTool) => void;
  showMasks: boolean;
  toggleShowMasks: () => void;
  showLabels: boolean;
  toggleShowLabels: () => void;
  filter: MaskRegionFilter;
  availableRegionKinds: string[];
  setFilterAll: () => void;
  setFilterByKind: (regionKind: string) => void;
  activeMaskId: string | null;
  setActiveMaskId: (regionId: string | null) => void;
  regions: PageRegion[];
  allRegions: PageRegion[];
  editablePolygonsByRegionId: Record<string, number[][]>;
  maskError: string | null;
  onRegionPolygonChange: (regionId: string, polygon: number[][]) => void;
  onRegionDelete: (regionId: string) => void;
  onRegionCreate: (kind: string, polygon: number[][]) => void;
  // Pen Settings
  penShape: "box" | "polygon" | null;
  setPenShape: (shape: "box" | "polygon") => void;
  penTarget: "panel" | "balloon" | "text";
  setPenTarget: (target: "panel" | "balloon" | "text") => void;
  // Typography
  textStylesByRegionId: Record<string, TypographyStyle>;
  globalTextStyle: TypographyStyle;
  setTextStyle: (style: Partial<TypographyStyle>) => void;
}

export interface MaskEditorController {
  workflow: WorkflowMaskController;
  workspace: WorkspaceMaskController;
}
