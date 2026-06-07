export { ApiError, toAbsoluteApiUrl } from "./api/core";
export {
  createProject,
  listProjects,
  deleteProject,
  getProject,
  getProjectEntry,
  createProjectChapter,
  listProjectChapters,
} from "./api/projects";
export {
  listChapterPages,
  listAllChapterPages,
  getPage,
  patchPageText,
  patchPageRegion,
  exportPagePsd,
  exportPageImage,
  savePageInpaintCleanup,
} from "./api/pages";
// Processing endpoints are grouped to scale with OCR/inpainting/mask tooling.
export { runMaskInference } from "./api/processing";
// Async job API — submit, poll, and SSE stream.
export { submitJob, getJobStatus, streamJobStatus } from "./api/jobs";
export { uploadSinglePage } from "./api/uploads";
export {
  createMemoryEntry,
  listMemoryEntries,
  updateMemoryEntry,
  deleteMemoryEntry,
} from "./api/memory";
