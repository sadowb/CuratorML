import { useCallback, useEffect, useRef, useState } from "react";
import { streamJobStatus } from "../../lib/api/jobs";
import type { JobSSEEvent } from "../../types/api";

type JobPhase = "idle" | "submitting" | "pending" | "running" | "completed" | "failed";

interface UseJobStatusReturn {
  /** Current phase of the most recent job. */
  phase: JobPhase;

  /** Human-readable detail string from the last SSE event. */
  detail: string | null;

  /** Arbitrary payload from the completed event (e.g. detection_count). */
  resultPayload: Record<string, unknown> | null;

  /** Error message if the job failed. */
  error: string | null;

  /**
   * Start tracking a new job.
   *
   * Call this right after `submitJob()` returns with a job_id.
   * When the job completes, `onCompleted` fires, then phase resets to idle.
   */
  trackJob: (jobId: string) => void;

  /** Reset state back to idle (e.g. when changing pages). */
  reset: () => void;
}

/**
 * React hook that tracks a background pipeline job via SSE.
 *
 * Usage:
 * ```tsx
 * const job = useJobStatus({ onCompleted: () => refreshPageDetail(pageId) });
 *
 * async function handleRunMask() {
 *   const { job_id } = await submitJob(pageId, "mask_inference");
 *   job.trackJob(job_id);
 * }
 * ```
 */
export function useJobStatus({
  onCompleted,
  onFailed,
}: {
  onCompleted?: () => void;
  onFailed?: (error: string) => void;
} = {}): UseJobStatusReturn {
  const [phase, setPhase] = useState<JobPhase>("idle");
  const [detail, setDetail] = useState<string | null>(null);
  const [resultPayload, setResultPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Keep stable refs to callbacks so they can change without re-subscribing.
  const onCompletedRef = useRef(onCompleted);
  onCompletedRef.current = onCompleted;
  const onFailedRef = useRef(onFailed);
  onFailedRef.current = onFailed;

  // Cleanup ref for the current SSE connection.
  const cleanupRef = useRef<(() => void) | null>(null);

  const reset = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setPhase("idle");
    setDetail(null);
    setResultPayload(null);
    setError(null);
  }, []);

  const trackJob = useCallback(
    (jobId: string) => {
      // Tear down any previous subscription.
      cleanupRef.current?.();
      setPhase("pending");
      setDetail("Job queued");
      setResultPayload(null);
      setError(null);

      const cleanup = streamJobStatus(
        jobId,
        (event: JobSSEEvent) => {
          setDetail(event.detail);

          if (event.status === "running") {
            setPhase("running");
          } else if (event.status === "completed") {
            setPhase("completed");
            setResultPayload(event.payload);
            onCompletedRef.current?.();

            // Auto-reset after a short delay so the UI can show "done" briefly.
            setTimeout(() => {
              setPhase("idle");
              setDetail(null);
            }, 1500);
          } else if (event.status === "failed") {
            setPhase("failed");
            setError(event.detail ?? "Job failed");
            onFailedRef.current?.(event.detail ?? "Job failed");
          }
        },
        () => {
          // SSE connection error — fall back to polling would go here,
          // but for now just mark as failed.
          setPhase("failed");
          setError("Lost connection to job stream");
        },
      );

      cleanupRef.current = cleanup;
    },
    [],
  );

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  return { phase, detail, resultPayload, error, trackJob, reset };
}
