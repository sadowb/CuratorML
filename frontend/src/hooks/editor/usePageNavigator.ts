import { useCallback, useTransition } from "react";
import type { NavigateFunction } from "react-router-dom";
import type { PageSummary } from "../../types/api";

interface UsePageNavigatorParams {
  projectId?: string;
  navigate: NavigateFunction;
  setActiveChapterId: (chapterId: string) => void;
  setCurrentPageNumber: (pageNumber: number) => void;
  refreshChapterPages: (chapterId: string) => Promise<PageSummary[]>;
}

export function usePageNavigator({
  projectId,
  navigate,
  setActiveChapterId,
  setCurrentPageNumber,
  refreshChapterPages,
}: UsePageNavigatorParams) {
  const [, startTransition] = useTransition();

  const handlePageSelect = useCallback(
    (nextPageId: string) => {
      if (!projectId) {
        return;
      }
      startTransition(() => {
        navigate(`/editor/${projectId}/${nextPageId}`);
      });
    },
    [navigate, projectId, startTransition],
  );

  const handleChapterChange = useCallback(
    async (chapterId: string) => {
      if (!projectId || !chapterId) {
        return;
      }

      setActiveChapterId(chapterId);
      const chapterPages = await refreshChapterPages(chapterId);

      if (chapterPages[0]) {
        setCurrentPageNumber(chapterPages[0].page_number);
        startTransition(() => {
          navigate(`/editor/${projectId}/${chapterPages[0].id}`);
        });
        return;
      }

      startTransition(() => {
        navigate(`/projects/${projectId}/upload?chapterId=${chapterId}`);
      });
    },
    [
      navigate,
      projectId,
      refreshChapterPages,
      setActiveChapterId,
      setCurrentPageNumber,
      startTransition,
    ],
  );

  return {
    handlePageSelect,
    handleChapterChange,
  };
}
