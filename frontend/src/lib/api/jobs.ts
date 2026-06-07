import { request, getApiBaseAttemptOrder } from "./core";
import type {
  InpaintOptionsPayload,
  JobSubmitResponse,
  JobStatusResponse,
  JobSSEEvent,
  TranslateOptionsPayload,
} from "../../types/api";

export type PipelineStage =
  | "mask_inference"
  | "ocr"
  | "inpaint"
  | "reading_order"
  | "translate"
  | "render_preview";

/**
 * Submit a new pipeline job for the given page.
 * Returns immediately with the job id (202 Accepted).
 */
export async function submitJob(
  pageId: string,
  stage: PipelineStage,
  stageOptions?: TranslateOptionsPayload | InpaintOptionsPayload,
  force: boolean = false,
): Promise<JobSubmitResponse> {
  const body: Record<string, unknown> = { stage, force };
  if (stage === "translate" && stageOptions) {
    body.translate_options = stageOptions as TranslateOptionsPayload;
  }
  if (stage === "inpaint" && stageOptions) {
    body.inpaint_options = stageOptions as InpaintOptionsPayload;
  }

  return request<JobSubmitResponse>(`/pages/${pageId}/jobs`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Poll current job status.
 */
export async function getJobStatus(
  jobId: string,
): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/jobs/${jobId}`);
}

/**
 * Open an SSE connection to stream real-time job status updates.
 *
 * Returns a cleanup function to close the connection.
 */
export function streamJobStatus(
  jobId: string,
  onEvent: (event: JobSSEEvent) => void,
  onError?: (error: Event) => void,
): () => void {
  const bases = getApiBaseAttemptOrder();
  const base = bases[0] ?? "http://127.0.0.1:8000/api/v1";
  const url = `${base}/jobs/${jobId}/stream`;

  const eventSource = new EventSource(url);

  eventSource.addEventListener("job_update", (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as JobSSEEvent;
      onEvent(data);

      // Auto-close on terminal status.
      if (data.status === "completed" || data.status === "failed") {
        eventSource.close();
      }
    } catch {
      // Ignore malformed events.
    }
  });

  eventSource.onerror = (event) => {
    onError?.(event);
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}

// Legacy endpoint — still works but prefer submitJob + streamJobStatus.
export { runMaskInference } from "./processing";
