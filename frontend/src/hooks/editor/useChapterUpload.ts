import { useEffect, useRef, useState } from "react";
import { uploadSinglePage } from "../../lib/api";
import { isSupportedImageUpload } from "../../lib/fileUpload";
import type { PageSummary } from "../../types/api";

interface UseChapterUploadParams {
  activeChapterId?: string;
  refreshChapterPages: (chapterId: string) => Promise<PageSummary[]>;
}

export function useChapterUpload({
  activeChapterId,
  refreshChapterPages,
}: UseChapterUploadParams) {
  const [isUploadingPages, setIsUploadingPages] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);

  const uploadNoticeTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (uploadNoticeTimerRef.current) {
        window.clearTimeout(uploadNoticeTimerRef.current);
      }
    };
  }, []);

  const setUploadNoticeWithTimeout = (message: string) => {
    if (uploadNoticeTimerRef.current) {
      window.clearTimeout(uploadNoticeTimerRef.current);
    }
    setUploadNotice(message);
    uploadNoticeTimerRef.current = window.setTimeout(() => {
      setUploadNotice(null);
    }, 3500);
  };

  const uploadPagesToActiveChapter = async (fileList: FileList | File[]) => {
    const chapterId = activeChapterId;
    if (!chapterId) {
      setUploadError("Select a chapter before uploading pages.");
      return;
    }

    const files = Array.from(fileList);
    if (files.length === 0) {
      return;
    }

    const invalidFile = files.find((file) => !isSupportedImageUpload(file));
    if (invalidFile) {
      setUploadError("Only PNG, JPG, and WEBP images are allowed.");
      return;
    }

    setUploadError(null);
    setUploadNotice(null);
    setIsUploadingPages(true);

    let uploadedCount = 0;
    let firstFailureMessage: string | null = null;

    for (const file of files) {
      try {
        await uploadSinglePage(chapterId, file);
        uploadedCount += 1;
      } catch (uploadFailure) {
        if (!firstFailureMessage) {
          firstFailureMessage =
            uploadFailure instanceof Error
              ? uploadFailure.message
              : `Failed to upload ${file.name}`;
        }
      }
    }

    try {
      await refreshChapterPages(chapterId);
    } catch {
      // Upload requests have already completed; this only affects immediate list refresh.
    }

    setIsUploadingPages(false);

    if (uploadedCount > 0) {
      const suffix = uploadedCount > 1 ? "pages" : "page";
      setUploadNoticeWithTimeout(
        `Uploaded ${uploadedCount} ${suffix} to this chapter.`,
      );
    }

    if (firstFailureMessage) {
      if (uploadedCount > 0) {
        const failedCount = files.length - uploadedCount;
        setUploadError(
          `${firstFailureMessage} (${failedCount} file${failedCount === 1 ? "" : "s"} failed).`,
        );
      } else {
        setUploadError(firstFailureMessage);
      }
    }
  };

  return {
    isUploadingPages,
    uploadError,
    uploadNotice,
    setUploadError,
    setUploadNotice,
    uploadPagesToActiveChapter,
  };
}
