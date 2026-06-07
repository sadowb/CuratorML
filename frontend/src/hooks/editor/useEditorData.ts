import { useEffect, useRef, useState } from "react";
import {
  getPage,
  getProject,
  listAllChapterPages,
} from "../../lib/api";
import type {
  Chapter,
  PageRegion,
  PageSummary,
  PageText,
} from "../../types/api";

function mergeDrafts(
  texts: PageText[],
  drafts: Record<string, Partial<PageText>>,
): PageText[] {
  return texts.map((text) => {
    const rawDraft = drafts[text.id] as (Partial<PageText> & { updatedAt?: number }) | undefined;
    if (!rawDraft) return text;

    // Ignore stale persisted drafts so fresh server-side translation results
    // are not masked in the editor after a completed background job.
    const draftUpdatedAt = typeof rawDraft.updatedAt === "number" ? rawDraft.updatedAt : 0;
    const textUpdatedAt = Date.parse(text.updated_at);
    if (
      draftUpdatedAt > 0 &&
      Number.isFinite(textUpdatedAt) &&
      draftUpdatedAt <= textUpdatedAt
    ) {
      return text;
    }

    const draft: Partial<PageText> = { ...rawDraft };
    delete (draft as Partial<PageText> & { updatedAt?: number }).updatedAt;
    return {
      ...text,
      ...draft,
    };
  });
}

function activeTextRegionIds(regions: PageRegion[]): Set<string> {
  return new Set(
    regions
      .filter((region) => region.is_active && region.region_kind === "text")
      .map((region) => region.id),
  );
}

function filterTextsForActiveTextRegions(
  texts: PageText[],
  regions: PageRegion[],
): PageText[] {
  const ids = activeTextRegionIds(regions);
  return texts.filter((text) => ids.has(text.region_id));
}

interface UseEditorDataParams {
  projectId?: string;
  pageId?: string;
  getPageDrafts: (pageId: string) => Record<string, Partial<PageText>>;
}

function appendCacheBuster(url: string, token: string | null | undefined): string {
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${encodeURIComponent(token)}`;
}

function resolveCurrentInpaintedImageUrl(
  files:
    | Array<{
        id: string;
        pipeline_run_id: string | null;
        created_at: string;
        file_kind: string;
        is_current: boolean;
        url: string | null;
      }>
    | undefined,
): string {
  if (!Array.isArray(files)) return "";
  const inpaintFile = files.find(
    (f) => f.file_kind === "inpainted" && f.is_current && Boolean(f.url),
  );
  if (!inpaintFile?.url) return "";

  const versionToken =
    inpaintFile.pipeline_run_id || inpaintFile.id || inpaintFile.created_at;

  return appendCacheBuster(inpaintFile.url ?? "", versionToken);
}

export function useEditorData({
  projectId,
  pageId,
  getPageDrafts,
}: UseEditorDataParams) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [activeChapterId, setActiveChapterId] = useState<string | undefined>(
    undefined,
  );
  const [pages, setPages] = useState<PageSummary[]>([]);
  const [imageUrl, setImageUrl] = useState<string>("");
  const [inpaintedImageUrl, setInpaintedImageUrl] = useState<string>("");
  const [texts, setTexts] = useState<PageText[]>([]);
  const [regions, setRegions] = useState<PageRegion[]>([]);
  const [currentStage, setCurrentStage] = useState<string>("");
  const [hasInpaintFile, setHasInpaintFile] = useState<boolean>(false);
  const [targetLanguage, setTargetLanguage] = useState<string>("en");
  const [readingDirection, setReadingDirection] = useState<"LTR" | "RTL">("LTR");
  const [currentPageNumber, setCurrentPageNumber] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedOnceRef = useRef(false);

  useEffect(() => {
    hasLoadedOnceRef.current = false;
    setIsLoading(true);
  }, [projectId]);

  const refreshChapterPages = async (
    chapterId: string,
  ): Promise<PageSummary[]> => {
    const chapterPages = await listAllChapterPages(chapterId);
    setPages(chapterPages);
    return chapterPages;
  };

  const refreshPageDetail = async (targetPageId: string) => {
    const page = await getPage(targetPageId);
    setImageUrl(page.original_file_url ?? "");
    setInpaintedImageUrl(resolveCurrentInpaintedImageUrl(page.files));
    setRegions(page.regions);
    setTexts(
      mergeDrafts(
        filterTextsForActiveTextRegions(page.texts, page.regions),
        getPageDrafts(page.id),
      ),
    );
    setCurrentPageNumber(page.page_number);
    setCurrentStage(page.current_stage ?? "");
    setHasInpaintFile(
      Array.isArray(page.files)
        ? page.files.some((f) => f.file_kind === "inpainted" && f.is_current)
        : false,
    );
    return page;
  };

  useEffect(() => {
    if (!projectId || !pageId) {
      return;
    }

    let isActive = true;

    const loadData = async () => {
      if (!hasLoadedOnceRef.current) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const [project, page] = await Promise.all([
          getProject(projectId),
          getPage(pageId),
        ]);
        if (!isActive) {
          return;
        }
        setChapters(project.chapters);
        setTargetLanguage(project.project.target_language || "en");
        setReadingDirection(project.project.reading_direction || "LTR");
        setActiveChapterId(page.chapter_id);
        setCurrentPageNumber(page.page_number);

        const chapterPages = await listAllChapterPages(page.chapter_id);
        if (!isActive) {
          return;
        }
        setPages(chapterPages);
        setImageUrl(page.original_file_url ?? "");
        setInpaintedImageUrl(resolveCurrentInpaintedImageUrl(page.files));
        setRegions(page.regions);
        setTexts(
          mergeDrafts(
            filterTextsForActiveTextRegions(page.texts, page.regions),
            getPageDrafts(page.id),
          ),
        );
        setCurrentStage(page.current_stage ?? "");
        setHasInpaintFile(
          Array.isArray(page.files)
            ? page.files.some((f) => f.file_kind === "inpainted" && f.is_current)
            : false,
        );
        hasLoadedOnceRef.current = true;
      } catch (loadError) {
        if (!isActive) {
          return;
        }
        const message =
          loadError instanceof Error
            ? loadError.message
            : "Failed to load editor data";
        setError(message);
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadData();
    return () => {
      isActive = false;
    };
  }, [projectId, pageId, getPageDrafts]);

  return {
    chapters,
    setChapters,
    activeChapterId,
    setActiveChapterId,
    pages,
    setPages,
    imageUrl,
    setImageUrl,
    inpaintedImageUrl,
    texts,
    setTexts,
    regions,
    setRegions,
    currentPageNumber,
    setCurrentPageNumber,
    isLoading,
    setIsLoading,
    error,
    setError,
    refreshChapterPages,
    refreshPageDetail,
    currentStage,
    hasInpaintFile,
    targetLanguage,
    readingDirection,
  };
}
