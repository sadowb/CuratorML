import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CreateChapterModal } from "../components/shared/CreateChapterModal";
import { Button } from "../components/ui/Button";
import { InlineAlert } from "../components/ui/InlineAlert";
import {
  createProjectChapter,
  getProject,
  listAllChapterPages,
  toAbsoluteApiUrl,
  uploadSinglePage,
} from "../lib/api";
import {
  clearPendingMemoryEntries,
  createMemoryEntriesBatch,
  loadPendingMemoryEntries,
  savePendingMemoryEntries,
  type StagedMemoryEntry,
} from "../lib/translationMemoryOnboarding";
import { formatFileSize, isSupportedImageUpload } from "../lib/fileUpload";
import type { Chapter, PageSummary } from "../types/api";

type UploadStatus = "pending" | "uploading" | "uploaded" | "error";

interface UploadEntry {
  id: string;
  file: File;
  previewUrl: string;
  progress: number;
  status: UploadStatus;
  error?: string;
  pageId?: string;
}

export default function UploadPages() {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedChapterId = searchParams.get("chapterId");

  const [projectName, setProjectName] = useState("");
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(
    requestedChapterId,
  );
  const [entries, setEntries] = useState<UploadEntry[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingPages, setExistingPages] = useState<PageSummary[]>([]);
  const [pendingMemoryRows, setPendingMemoryRows] = useState<StagedMemoryEntry[]>([]);
  const [memoryRetryNotice, setMemoryRetryNotice] = useState<string | null>(null);
  const [memoryRetryError, setMemoryRetryError] = useState<string | null>(null);
  const [isRetryingMemory, setIsRetryingMemory] = useState(false);

  const [isChapterModalOpen, setIsChapterModalOpen] = useState(false);
  const [isSubmittingChapter, setIsSubmittingChapter] = useState(false);
  const [chapterTitle, setChapterTitle] = useState("");
  const [chapterNumber, setChapterNumber] = useState(1);

  const getNextChapterNumber = (chaps: Chapter[]) =>
    chaps.length === 0 ? 1 : Math.max(...chaps.map((c) => c.chapter_number)) + 1;

  const openCreateChapterModal = () => {
    if (!projectId) return;
    const nextNumber = getNextChapterNumber(chapters);
    setChapterNumber(nextNumber);
    setChapterTitle(`Chapter ${nextNumber}`);
    setIsChapterModalOpen(true);
    setError(null);
  };

  const closeChapterModal = () => {
    setIsChapterModalOpen(false);
    setIsSubmittingChapter(false);
  };

  const submitChapterModal = async () => {
    if (!projectId) return;
    if (!chapterTitle.trim()) {
      setError("Chapter title is required.");
      return;
    }
    
    setIsSubmittingChapter(true);
    setError(null);
    try {
      const created = await createProjectChapter(projectId, {
        title: chapterTitle.trim(),
        chapter_number: chapterNumber,
      });
      const refreshedProject = await getProject(projectId);
      setChapters([...refreshedProject.chapters].sort((a, b) => a.chapter_number - b.chapter_number));
      setSelectedChapterId(created.id);
      setSearchParams({ chapterId: created.id });
      setExistingPages([]);
      closeChapterModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create chapter");
      setIsSubmittingChapter(false);
    }
  };

  const uploadedEntries = useMemo(
    () => entries.filter((entry) => entry.status === "uploaded"),
    [entries],
  );
  const selectedChapter = useMemo(
    () => chapters.find((chapter) => chapter.id === selectedChapterId) ?? null,
    [chapters, selectedChapterId],
  );

  useEffect(() => {
    return () => {
      entries.forEach((entry) => {
        URL.revokeObjectURL(entry.previewUrl);
      });
    };
  }, [entries]);

  useEffect(() => {
    if (!projectId) {
      return;
    }

    const loadProject = async () => {
      try {
        const project = await getProject(projectId);
        const orderedChapters = [...project.chapters].sort((a, b) => a.chapter_number - b.chapter_number);
        setProjectName(project.project.name);
        setChapters(orderedChapters);

        const fallbackChapterId =
          requestedChapterId ?? orderedChapters[0]?.id ?? null;
        setSelectedChapterId(fallbackChapterId);

        if (fallbackChapterId) {
          const pages = await listAllChapterPages(fallbackChapterId);
          setExistingPages(pages);
        } else {
          setExistingPages([]);
        }
      } catch (fetchError) {
        const message =
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load chapter information";
        setError(message);
      }
    };

    void loadProject();
  }, [projectId, requestedChapterId]);

  useEffect(() => {
    if (!projectId) return;
    const pendingRows = loadPendingMemoryEntries(projectId);
    setPendingMemoryRows(pendingRows);

    const memoryRetry = searchParams.get("memoryRetry");
    const failedCount = searchParams.get("memoryFailedCount");
    if (memoryRetry === "1" && pendingRows.length > 0) {
      const count = failedCount ? Number(failedCount) : pendingRows.length;
      setMemoryRetryNotice(
        `${Number.isFinite(count) ? count : pendingRows.length} translation memory entries still need retry.`,
      );
    }
  }, [projectId, searchParams]);

  const addFiles = (fileList: FileList | File[]) => {
    const files = Array.from(fileList);
    if (files.length === 0) {
      return;
    }

    const invalidFile = files.find((file) => !isSupportedImageUpload(file));
    if (invalidFile) {
      setError("Only PNG, JPG, and WEBP images are allowed.");
      return;
    }

    setError(null);
    setEntries((prev) => [
      ...prev,
      ...files.map((file) => ({
        id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        previewUrl: URL.createObjectURL(file),
        progress: 0,
        status: "pending" as const,
      })),
    ]);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    addFiles(event.dataTransfer.files);
  };

  const onFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files) {
      return;
    }
    addFiles(event.target.files);
    event.target.value = "";
  };

  const loadPagesForChapter = async (chapterId: string) => {
    const pages = await listAllChapterPages(chapterId);
    setExistingPages(pages);
  };

  const onChapterSelect = async (chapterId: string) => {
    setSelectedChapterId(chapterId);
    setSearchParams({ chapterId });
    await loadPagesForChapter(chapterId);
  };


  const uploadAll = async () => {
    const chapterId = selectedChapterId;
    if (!chapterId) {
      setError("Create or select a chapter first.");
      return;
    }

    const pendingEntries = entries.filter(
      (entry) => entry.status === "pending" || entry.status === "error",
    );
    if (pendingEntries.length === 0) {
      return;
    }

    setError(null);
    setIsUploading(true);

    const successfulPageIds: string[] = [];

    for (const pending of pendingEntries) {
      setEntries((prev) =>
        prev.map((entry) =>
          entry.id === pending.id
            ? {
                ...entry,
                status: "uploading",
                progress: 0,
                error: undefined,
              }
            : entry,
        ),
      );

      try {
        const uploaded = await uploadSinglePage(
          chapterId,
          pending.file,
          (percent) => {
            setEntries((prev) =>
              prev.map((entry) =>
                entry.id === pending.id
                  ? { ...entry, progress: percent }
                  : entry,
              ),
            );
          },
        );

        successfulPageIds.push(uploaded.page.id);
        setEntries((prev) =>
          prev.map((entry) =>
            entry.id === pending.id
              ? {
                  ...entry,
                  status: "uploaded",
                  progress: 100,
                  pageId: uploaded.page.id,
                }
              : entry,
          ),
        );
      } catch (uploadError) {
        const message =
          uploadError instanceof Error ? uploadError.message : "Upload failed";
        setEntries((prev) =>
          prev.map((entry) =>
            entry.id === pending.id
              ? {
                  ...entry,
                  status: "error",
                  error: message,
                }
              : entry,
          ),
        );
      }
    }

    setIsUploading(false);

    if (successfulPageIds.length > 0) {
      await loadPagesForChapter(chapterId);
    }
  };

  const openEditor = () => {
    if (!projectId) {
      return;
    }

    const pageId = uploadedEntries[0]?.pageId ?? existingPages[0]?.id;
    if (!pageId) {
      setError("No uploaded page is available yet.");
      return;
    }

    navigate(`/editor/${projectId}/${pageId}`);
  };

  const clearMemoryRetryQueryParams = () => {
    setSearchParams((prev) => {
      prev.delete("memoryRetry");
      prev.delete("memoryFailedCount");
      return prev;
    });
  };

  const retryPendingMemorySave = async () => {
    if (!projectId || pendingMemoryRows.length === 0) {
      return;
    }
    const retryChapter = chapters.find((chapter) => chapter.id === (requestedChapterId ?? selectedChapterId));
    const chapterNumber = retryChapter?.chapter_number ?? selectedChapter?.chapter_number ?? 1;

    setIsRetryingMemory(true);
    setMemoryRetryError(null);
    setMemoryRetryNotice(null);
    try {
      const result = await createMemoryEntriesBatch(
        projectId,
        chapterNumber,
        pendingMemoryRows,
        4,
      );
      const failedRows = result.failed.map((item) => item.entry);
      if (failedRows.length > 0) {
        savePendingMemoryEntries(projectId, failedRows);
        setPendingMemoryRows(failedRows);
        setMemoryRetryError(
          `${failedRows.length} memory entr${failedRows.length === 1 ? "y" : "ies"} still failed. You can retry again.`,
        );
      } else {
        clearPendingMemoryEntries(projectId);
        setPendingMemoryRows([]);
        setMemoryRetryNotice("All pending translation memory entries were saved.");
        clearMemoryRetryQueryParams();
      }
    } catch (err) {
      setMemoryRetryError(
        err instanceof Error ? err.message : "Failed to retry memory save.",
      );
    } finally {
      setIsRetryingMemory(false);
    }
  };

  return (
    <div className="scrollbar-hide h-full w-full overflow-y-auto bg-[radial-gradient(circle_at_88%_0%,_#fceff4_0%,_#fbfbfb_42%,_#f5f4f0_100%)] px-4 py-8 text-brand-text lg:px-6">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-7">
        <div className="flex items-end justify-between gap-6 flex-wrap">
          <div>
            <h1 className="text-[42px] font-serif text-gray-900 tracking-tight leading-none mb-3">
              Upload Chapter Pages
            </h1>
            <p className="text-[14px] text-gray-600 font-medium">
              Add chapters and upload pages in one flow without leaving this
              screen.
            </p>
            <p className="mt-2 text-xs uppercase tracking-[0.1em] text-[#6b2d3c]">
              {projectName}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => navigate("/dashboard")}>
              Back to Dashboard
            </Button>
            <Button
              onClick={openEditor}
              disabled={
                uploadedEntries.length === 0 && existingPages.length === 0
              }
            >
              Open in Editor
            </Button>
          </div>
        </div>

        {error ? <InlineAlert>{error}</InlineAlert> : null}

        {pendingMemoryRows.length > 0 ? (
          <div className="rounded-[14px] border border-[#e4cf9d] bg-[#fff9e8] p-4 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.3)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[#8a5b00]">
                  Translation Memory Retry
                </h3>
                <p className="mt-1 text-sm text-[#6c5b39]">
                  {memoryRetryNotice ??
                    `${pendingMemoryRows.length} memory entr${pendingMemoryRows.length === 1 ? "y is" : "ies are"} pending from project setup.`}
                </p>
                {memoryRetryError ? (
                  <p className="mt-1 text-sm text-red-600">{memoryRetryError}</p>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="pill"
                  onClick={clearMemoryRetryQueryParams}
                >
                  Dismiss
                </Button>
                <Button onClick={() => void retryPendingMemorySave()} disabled={isRetryingMemory}>
                  {isRetryingMemory ? "Retrying..." : "Retry Save Memory"}
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap items-end gap-3 rounded-[18px] border border-[#e3d2d8] bg-[#fff9fb] px-5 py-4 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.45)]">
          <div className="flex flex-col gap-1 min-w-[240px]">
            <label
              htmlFor="chapter-picker"
              className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6b2d3c]"
            >
              Active Chapter
            </label>
            <select
              id="chapter-picker"
              className="h-10 rounded-xl border border-[#d8c7cd] bg-white px-3 text-sm text-[#2d151d] shadow-sm"
              value={selectedChapterId ?? ""}
              onChange={(event) => void onChapterSelect(event.target.value)}
            >
              {chapters.length === 0 ? (
                <option value="">No chapter yet</option>
              ) : null}
              {chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  Ch.{chapter.chapter_number} - {chapter.title}
                </option>
              ))}
            </select>
          </div>
          <Button variant="outline" size="pill" onClick={openCreateChapterModal}>
            Add Chapter
          </Button>
          {selectedChapter ? (
            <span className="pb-1 text-sm font-medium text-[#5e4f56]">
              Uploading into Chapter {selectedChapter.chapter_number}.
            </span>
          ) : null}
        </div>

        <div
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          className="rounded-[18px] border border-[#e3d2d8] bg-[#fff9fb] p-5 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.45)]"
        >
          <div className="flex flex-col items-center gap-4 rounded-[18px] border border-dashed border-[#dcc7cf] bg-white px-6 py-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f7ecef] text-[#6b2d3c]">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" x2="12" y1="3" y2="15" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[#2d151d]">
                Drop PNG, JPG, or WEBP files here
              </h2>
              <p className="mt-1 text-sm text-[#6e5b62]">
                You can keep uploading chapter-by-chapter from this same screen.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <label
                htmlFor="upload-pages-input"
                className="inline-flex h-10 cursor-pointer items-center justify-center rounded-full border border-[#d8c7cd] bg-white px-5 text-sm font-semibold text-[#2d151d] transition-colors hover:bg-[#f7ecef]"
              >
                Browse Files
                <input
                  id="upload-pages-input"
                  name="upload_pages"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  multiple
                  className="hidden"
                  onChange={onFileInputChange}
                />
              </label>
              <Button
                onClick={uploadAll}
                disabled={entries.length === 0 || isUploading || !selectedChapterId}
              >
                {isUploading ? "Uploading..." : "Upload Selected Files"}
              </Button>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-5 rounded-[18px] border border-[#e3d2d8] bg-[#fff9fb] p-5 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.4)]">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6b2d3c]">
              Upload Queue
            </h3>
          </div>

          {entries.length === 0 ? (
            <p className="text-sm text-brand-text-muted">
              No files selected yet.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {entries.map((entry) => (
                <article
                  key={entry.id}
                  className="rounded-xl border border-gray-200 p-4 flex gap-4 items-start"
                >
                  <img
                    src={entry.previewUrl}
                    alt={entry.file.name}
                    className="w-20 h-20 object-cover rounded-md border border-gray-200"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {entry.file.name}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatFileSize(entry.file.size)}
                    </p>
                    <div className="mt-3 h-2 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={`h-full transition-all ${entry.status === "error" ? "bg-red-400" : "bg-brand-gold"}`}
                        style={{ width: `${entry.progress}%` }}
                      />
                    </div>
                    <p className="text-xs mt-2 text-gray-600 capitalize">
                      {entry.status}
                    </p>
                    {entry.error && (
                      <p className="text-xs text-red-600 mt-1">{entry.error}</p>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        {existingPages.length > 0 ? (
          <div className="flex flex-col gap-4 rounded-[18px] border border-[#e3d2d8] bg-white p-5 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.3)]">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6b2d3c]">
              Uploaded Pages
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              {existingPages.map((page) => (
                <button
                  key={page.id}
                  onClick={() => navigate(`/editor/${projectId}/${page.id}`)}
                  className="rounded-xl border border-[#e3d2d8] p-2 text-left transition-colors hover:border-[#b88b97] hover:bg-[#fff9fb]"
                >
                  <div className="aspect-[3/4] bg-gray-100 rounded-md overflow-hidden">
                    {page.original_file_url ? (
                      <img
                        src={toAbsoluteApiUrl(page.original_file_url)}
                        alt={`Page ${page.page_number}`}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                        No preview
                      </div>
                    )}
                  </div>
                  <p className="mt-2 text-xs font-semibold text-gray-700">
                    Page {page.page_number}
                  </p>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <CreateChapterModal
        isOpen={isChapterModalOpen}
        description="Create chapter and keep uploading in this same flow."
        chapterTitle={chapterTitle}
        onChapterTitleChange={setChapterTitle}
        chapterNumber={chapterNumber}
        onChapterNumberChange={(val) => setChapterNumber(Math.max(1, Number(val) || 1))}
        onClose={closeChapterModal}
        onSubmit={() => void submitChapterModal()}
        isSubmitting={isSubmittingChapter}
      />
    </div>
  );
}
