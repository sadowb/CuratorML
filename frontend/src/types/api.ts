export interface Chapter {
  id: string;
  project_id: string;
  title: string;
  chapter_number: number;
  chapter_status: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  user_id: string | null;
  name: string;
  source_language: string;
  target_language: string;
  reading_direction: "LTR" | "RTL";
  project_status: string;
  context: string | null;
  enable_ocr: boolean;
  require_qc: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectListItem extends Project {
  chapter_count: number;
  page_count: number;
}

export interface ProjectCreatePayload {
  name: string;
  source_language: string;
  target_language: string;
  reading_direction: "LTR" | "RTL";
  chapter_title: string;
  chapter_number: number;
  estimated_pages?: number;
  context?: string;
  enable_ocr: boolean;
  require_qc: boolean;
}

export interface ProjectCreateResponse {
  project: Project;
  chapter: Chapter;
}

export interface ProjectWithChapters {
  project: Project;
  chapters: Chapter[];
}

export interface ProjectEntry {
  project_id: string;
  chapter_id: string | null;
  page_id: string | null;
  editor_url: string | null;
  upload_url: string | null;
  reason: "editor_ready" | "upload_required" | "chapter_required" | string;
}

export interface ChapterCreatePayload {
  title: string;
  chapter_number: number;
}

export interface PageFile {
  id: string;
  page_id: string;
  pipeline_run_id: string | null;
  file_kind: string;
  file_path: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  is_current: boolean;
  created_at: string;
  url: string | null;
}

export interface PageText {
  id: string;
  region_id: string;
  pipeline_run_id: string | null;
  ocr_text_raw: string | null;
  ocr_text_corrected: string | null;
  ocr_confidence: number | null;
  context_notes: string | null;
  translation_draft: string | null;
  translation_corrected: string | null;
  display_text_final: string | null;
  render_scale: number | null;
  render_color: string | null;
  render_font_family: string | null;
  render_font_weight?: "normal" | "bold" | null;
  render_bounds?: [number, number, number, number] | null;
  translation_status: string;
  created_at: string;
  updated_at: string;
}

export interface PageRegion {
  id: string;
  page_id: string;
  parent_region_id: string | null;
  pipeline_run_id: string | null;
  created_by_user_id: string | null;
  region_kind: string;
  polygon_json: number[][] | null;
  bbox_json: number[] | null;
  confidence: number | null;
  reading_order: number | null;
  origin: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PageSummary {
  id: string;
  chapter_id: string;
  page_number: number;
  current_stage: string;
  review_status: string;
  created_at: string;
  updated_at: string;
  original_file_url: string | null;
}

export interface PagePagination {
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedPageSummaryResponse {
  items: PageSummary[];
  pagination: PagePagination;
}

export interface PageDetail extends PageSummary {
  files: PageFile[];
  texts: PageText[];
  regions: PageRegion[];
}

export interface PageUploadItem {
  page: PageSummary;
  file: PageFile;
}

export interface PageUploadResponse {
  items: PageUploadItem[];
}

export interface PageTextPatchPayload {
  ocr_text_corrected?: string | null;
  translation_corrected?: string | null;
  display_text_final?: string | null;
  translation_status?: string;
  context_notes?: string | null;
  render_scale?: number;
  render_color?: string | null;
  render_font_family?: string | null;
  render_font_weight?: "normal" | "bold" | null;
  render_bounds?: [number, number, number, number] | null;
}

export interface PageRegionPatchPayload {
  polygon_json?: number[][];
  bbox_json?: number[];
  region_kind?: string;
  confidence?: number;
  is_active?: boolean;
}

export interface PageRegionCreatePayload {
  region_kind: string;
  polygon_json?: number[][];
  bbox_json?: number[];
  confidence?: number;
  reading_order?: number;
  parent_region_id?: string;
}

export interface MaskDetection {
  id: number;
  region_kind: string;
  box: number[];
  conf: number;
  mask: number[][];
}

export interface MaskInferenceResponse {
  pipeline_run_id: string;
  page_id: string;
  stage: string;
  detections: MaskDetection[];
}

// ---------------------------------------------------------------------------
// Job / Pipeline API types
// ---------------------------------------------------------------------------

export interface JobSubmitResponse {
  job_id: string;
  page_id: string;
  stage: string;
  status: string;
}

export interface JobStatusResponse {
  job_id: string;
  page_id: string;
  stage: string;
  status: string;
  model_name: string | null;
  error_message: string | null;
  metrics_json: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface JobSSEEvent {
  job_id: string;
  status: string;
  detail: string | null;
  payload: Record<string, unknown> | null;
}

export interface ProviderOverridePayload {
  provider_mode: "compatible_local" | "openai_official";
  base_url?: string;
}

export interface TranslateOptionsPayload {
  target_language: string;
  story_context?: string;
  model?: string;
  enable_thinking?: boolean;
  force_overwrite_draft?: boolean;
  retry_missing_only?: boolean;
  provider_override?: ProviderOverridePayload;
}

export interface InpaintOptionsPayload {
  method?: "telea" | "ns";
  radius?: number;
  ai_expand_strength?: number;
  text_expand_px?: number;
  balloon_safe_inset_mode?: "auto" | "manual";
  balloon_safe_inset_px?: number;
  clip_fallback_mode?: "no_clip" | "inset_bbox";
}

export interface PageInpaintCleanupPayload {
  image_data_url: string;
}

export interface PageInpaintCleanupResponse {
  page_id: string;
  file: PageFile;
}

export interface PsdExportRequestPayload {
  include_preview?: boolean;
  include_ocr_notes?: boolean;
  include_brush_cleanup?: boolean;
  include_merged_preview?: boolean;
  original_visible?: boolean;
  inpainted_visible?: boolean;
}

export interface PsdExportCanvas {
  width: number;
  height: number;
}

export interface PsdExportOutputs {
  psd_path: string;
  manifest_path: string;
  psd_url: string;
  manifest_url: string;
}

export interface PsdExportResponse {
  export_id: string;
  page_id: string;
  writer: string;
  writer_version: string;
  canvas: PsdExportCanvas;
  outputs: PsdExportOutputs;
  layer_count: number;
  manifest: Record<string, unknown>;
}

export type ImageExportFormat = "png" | "jpg" | "jpeg" | "webp" | "pdf";

export interface ImageExportRequestPayload {
  format: ImageExportFormat;
}

export interface ImageExportResponse {
  export_id: string;
  page_id: string;
  format: "png" | "jpg" | "webp" | "pdf";
  file_kind: string;
  file_path: string;
  file_url: string;
}

export type MemoryEntryType =
  | "character"
  | "attack"
  | "place"
  | "organization";

export interface TranslationMemoryEntry {
  id: string;
  project_id: string;
  entry_type: MemoryEntryType;
  source_term: string;
  preferred_translation: string;
  scope_chapter: number | null;
  aliases: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranslationMemoryEntryCreatePayload {
  entry_type: MemoryEntryType;
  source_term: string;
  preferred_translation: string;
  scope_chapter?: number | null;
  aliases?: string[];
  notes?: string | null;
}

export interface TranslationMemoryEntryUpdatePayload {
  entry_type?: MemoryEntryType;
  source_term?: string;
  preferred_translation?: string;
  scope_chapter?: number | null;
  aliases?: string[];
  notes?: string | null;
}
