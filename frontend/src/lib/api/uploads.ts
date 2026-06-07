import {
  ApiError,
  extractApiErrorMessage,
  getApiBaseAttemptOrder,
  isLikelyHtmlContentType,
  setActiveApiBase,
} from "./core";
import type { PageUploadItem, PageUploadResponse } from "../../types/api";

type UploadAttemptResult =
  | { kind: "success"; item: PageUploadItem }
  | { kind: "retry" }
  | { kind: "error"; error: ApiError };

function uploadSinglePageAgainstBase(
  base: string,
  chapterId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadAttemptResult> {
  return new Promise((resolve) => {
    const formData = new FormData();
    formData.append("files", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${base}/chapters/${chapterId}/pages/upload`);

    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) {
        return;
      }
      const percent = Math.round((event.loaded / event.total) * 100);
      onProgress(percent);
    };

    xhr.onerror = () => {
      resolve({ kind: "retry" });
    };

    xhr.onload = () => {
      const contentType = xhr.getResponseHeader("Content-Type");
      const htmlResponse = isLikelyHtmlContentType(contentType);

      if (xhr.status < 200 || xhr.status >= 300) {
        if (htmlResponse) {
          resolve({ kind: "retry" });
          return;
        }

        resolve({
          kind: "error",
          error: new ApiError(
            extractApiErrorMessage(xhr.responseText, "Upload failed"),
            xhr.status,
          ),
        });
        return;
      }

      if (htmlResponse) {
        resolve({ kind: "retry" });
        return;
      }

      let payload: PageUploadResponse;
      try {
        payload = JSON.parse(xhr.responseText) as PageUploadResponse;
      } catch {
        resolve({ kind: "retry" });
        return;
      }

      const firstItem = payload.items[0];
      if (!firstItem) {
        resolve({
          kind: "error",
          error: new ApiError(
            "Upload succeeded but returned no page",
            xhr.status,
          ),
        });
        return;
      }

      resolve({ kind: "success", item: firstItem });
    };

    xhr.send(formData);
  });
}

export async function uploadSinglePage(
  chapterId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<PageUploadItem> {
  const candidateOrder = getApiBaseAttemptOrder();

  for (const base of candidateOrder) {
    const attempt = await uploadSinglePageAgainstBase(
      base,
      chapterId,
      file,
      onProgress,
    );

    if (attempt.kind === "retry") {
      continue;
    }

    if (attempt.kind === "error") {
      throw attempt.error;
    }

    setActiveApiBase(base);
    onProgress?.(100);
    return attempt.item;
  }

  throw new ApiError(
    `Network error while uploading file (attempted: ${candidateOrder.join(", ")})`,
    0,
  );
}
