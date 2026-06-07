import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import BottomBar from "../components/MangaEditor/BottomBar";
import RightSidebar from "../components/MangaEditor/RightSidebar";
import TopHeader from "../components/MangaEditor/TopHeader";
import Workspace from "../components/MangaEditor/Workspace";
import { CreateChapterModal } from "../components/shared/CreateChapterModal";
import { createProjectChapter, exportPagePsd, toAbsoluteApiUrl } from "../lib/api";
import { useEditorAutosave } from "../hooks/editor/useEditorAutosave";
import { useEditorData } from "../hooks/editor/useEditorData";
import { useMaskEditorController } from "../hooks/editor/useMaskEditorController";
import { useChapterUpload } from "../hooks/editor/useChapterUpload";
import { usePageNavigator } from "../hooks/editor/usePageNavigator";
import { useDragUpload } from "../hooks/useDragUpload";
import { useEditorStore } from "../store/useEditorStore";
import {
  buildOrderedOcrItems,
  buildReadingOrderLabelsByRegionId,
} from "../lib/ocrOrdering";
import type { OcrSidebarItem } from "../components/MangaEditor/RightSidebar";

export default function MangaEditor() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { projectId, pageId } = useParams<{
    projectId: string;
    pageId: string;
  }>();
  const {
    getPageDrafts,
    upsertDraft,
    clearDraft,
    viewMode,
    activeWorkflow,
    setTextPlacementMode,
    clearTextOffset,
    clearTextBoxSize,
    getPageTextPlacementModes,
    inpaintSettings,
    setInpaintSettings,
    translationSettings,
    setTranslationSettings,
  } = useEditorStore();

  // -- Data ----------------------------------------------------------------
  const {
    chapters,
    activeChapterId,
    setActiveChapterId,
    pages,
    imageUrl,
    inpaintedImageUrl,
    texts,
    setTexts,
    regions,
    setCurrentPageNumber,
    isLoading,
    error,
    refreshChapterPages,
    refreshPageDetail,
    targetLanguage,
    readingDirection,
  } = useEditorData({ projectId, pageId, getPageDrafts });

  // Derived pipeline state for gating workflow steps
  const hasMaskRegions = regions.some((r) => r.origin === "mask_inference" && r.is_active);
  const hasOCRTexts = texts.some((t) => Boolean(t.ocr_text_raw));
  const hasInpaintedImage = Boolean(inpaintedImageUrl);
  const [selectedTextRegionId, setSelectedTextRegionId] = useState<string | null>(null);
  const [psdExportError, setPsdExportError] = useState<string | null>(null);
  const [psdExportNotice, setPsdExportNotice] = useState<string | null>(null);
  const workspaceImageUrl =
    viewMode === "Translated" && inpaintedImageUrl
      ? inpaintedImageUrl
      : imageUrl || inpaintedImageUrl;

  useEffect(() => {
    setSelectedTextRegionId(null);
    setPsdExportError(null);
    setPsdExportNotice(null);
  }, [pageId]);

  const ocrSidebarItems = useMemo<OcrSidebarItem[]>(
    () => buildOrderedOcrItems(texts, regions, readingDirection),
    [regions, texts, readingDirection],
  );

  const readingOrderLabelsByRegionId = useMemo(
    () => buildReadingOrderLabelsByRegionId(ocrSidebarItems),
    [ocrSidebarItems],
  );
  const textScaleByTextId = useMemo(
    () =>
      Object.fromEntries(
        texts.map((text) => [text.id, text.render_scale ?? 1]),
      ),
    [texts],
  );
  const textColorByTextId = useMemo(
    () =>
      Object.fromEntries(
        texts.map((text) => [text.id, text.render_color ?? "#111111"]),
      ),
    [texts],
  );
  const textFontByTextId = useMemo(
    () =>
      Object.fromEntries(
        texts.map((text) => [
          text.id,
          text.render_font_family ??
            "\"Komika Text\", \"Comic Sans MS\", \"Trebuchet MS\", sans-serif",
        ]),
      ),
    [texts],
  );
  const textFontWeightByTextId = useMemo(
    () =>
      Object.fromEntries(
        texts.map((text) => [text.id, text.render_font_weight ?? "normal"]),
      ) as Record<string, "normal" | "bold">,
    [texts],
  );
  const placementModeByRegionId = pageId ? getPageTextPlacementModes(pageId) : {};

  const {
    saveState,
    handleTextChange,
    handleTranslatedTextChange,
    handleTextScaleChange,
    handleTextColorChange,
    handleTextFontChange,
    handleTextFontWeightChange,
    handleRenderBoundsChange,
    flushPendingSaves,
  } = useEditorAutosave({
    pageId,
    setTexts,
    upsertDraft,
    clearDraft,
  });

  const {
    isUploadingPages,
    uploadError,
    uploadNotice,
    setUploadNotice,
    uploadPagesToActiveChapter,
  } = useChapterUpload({ activeChapterId, refreshChapterPages });

  const { handlePageSelect, handleChapterChange } = usePageNavigator({
    projectId,
    navigate,
    setActiveChapterId,
    setCurrentPageNumber,
    refreshChapterPages,
  });

  const maskEditor = useMaskEditorController({
    pageId,
    targetLanguage,
    translationEnableThinking: translationSettings.enable_thinking,
    inpaintOptions: inpaintSettings,
    regions,
    refreshPageDetail,
  });

  // -- Drag upload ---------------------------------------------------------
  const { isDragActive, dragHandlers } = useDragUpload(
    (files) => void uploadPagesToActiveChapter(files),
  );

  // -- Chapter creation modal ----------------------------------------------
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [newChapterNumber, setNewChapterNumber] = useState(1);

  const openCreateModal = () => {
    const next =
      chapters.length > 0
        ? Math.max(...chapters.map((c) => c.chapter_number)) + 1
        : 1;
    setNewChapterNumber(next);
    setNewChapterTitle(`Chapter ${next}`);
    setIsCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
  };

  const createChapterMutation = useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error("Project ID is missing");
      if (!newChapterTitle.trim()) throw new Error("Chapter title is required");

      return createProjectChapter(projectId, {
        title: newChapterTitle.trim(),
        chapter_number: newChapterNumber,
      });
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setUploadNotice("Chapter created. Continue by uploading pages to it.");
      closeCreateModal();
      navigate(`/projects/${projectId}/upload?chapterId=${created.id}`);
    },
    onError: (err) => {
      setUploadNotice(
        err instanceof Error ? err.message : "Failed to create chapter",
      );
    },
  });

  const exportPsdMutation = useMutation({
    mutationFn: async () => {
      if (!pageId) {
        throw new Error("Select a page before exporting PSD.");
      }
      const saved = await flushPendingSaves();
      if (!saved) {
        throw new Error("Please resolve autosave errors before exporting.");
      }
      return exportPagePsd(pageId, {});
    },
    onMutate: () => {
      setPsdExportError(null);
      setPsdExportNotice(null);
    },
    onSuccess: (result) => {
      const downloadUrl = toAbsoluteApiUrl(result.outputs.psd_url);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setPsdExportNotice(
        `PSD exported with ${result.layer_count} layer${result.layer_count === 1 ? "" : "s"}.`,
      );
    },
    onError: (err) => {
      setPsdExportError(
        err instanceof Error ? err.message : "Failed to export PSD.",
      );
    },
  });

  const exportImageMutation = useMutation({
    mutationFn: async (format: "png" | "jpg" | "webp" | "pdf") => {
      const saved = await flushPendingSaves();
      if (!saved) {
        throw new Error("Please resolve autosave errors before exporting.");
      }

      const target = document.querySelector('[data-export-target="workspace-canvas"]') as HTMLElement | null;
      if (!target) {
        throw new Error("Export target not found in workspace.");
      }
      const baseImage = target.querySelector("img") as HTMLImageElement | null;
      const displayedW = Math.max(1, target.clientWidth);
      const displayedH = Math.max(1, target.clientHeight);
      const naturalW = baseImage?.naturalWidth ?? displayedW;
      const naturalH = baseImage?.naturalHeight ?? displayedH;
      if (baseImage && !baseImage.complete) {
        await baseImage.decode().catch(() => undefined);
      }
      // Ensure custom fonts (Komika Text, Comic Sans MS, etc.) are fully loaded
      // before capture — prevents fallback-font substitution that shifts glyph metrics.
      await document.fonts.ready;
      // Two rAFs: first lets layout settle, second ensures paint is committed.
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      );

      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);

      const nativeRatio = Math.max(naturalW / displayedW, naturalH / displayedH, 1);
      // Keep capture stable by sizing to rendered viewport and using scale for quality.
      const captureScale = Math.max(2, Math.min(6, nativeRatio));
      console.log(
        `[export] src=${baseImage?.src ?? "none"} complete=${baseImage?.complete} ` +
        `natural=${naturalW}x${naturalH} display=${displayedW}x${displayedH} scale=${captureScale}`,
      );
      const canvas = await html2canvas(target, {
        backgroundColor: "#ffffff",
        scale: captureScale,
        useCORS: true,
        logging: false,
        foreignObjectRendering: false,
        imageTimeout: 15000,
        width: displayedW,
        height: displayedH,
        windowWidth: displayedW,
        windowHeight: displayedH,
        onclone: (doc) => {
          doc
            .querySelectorAll(".translated-text-draggable, [data-export-hide='true']")
            .forEach((el) => {
              (el as HTMLElement).style.display = "none";
            });
        },
      });

      const safePageId = pageId ?? "page";
      const base = `page-${safePageId}-translated`;

      if (format === "pdf") {
        const pdf = new jsPDF({
          orientation: canvas.width >= canvas.height ? "landscape" : "portrait",
          unit: "px",
          format: [canvas.width, canvas.height],
          compress: true,
        });
        const pngData = canvas.toDataURL("image/png");
        pdf.addImage(pngData, "PNG", 0, 0, canvas.width, canvas.height);
        pdf.save(`${base}.pdf`);
        return { format: "pdf" as const };
      }

      const mimeType =
        format === "jpg"
          ? "image/jpeg"
          : format === "webp"
            ? "image/webp"
            : "image/png";
      const quality = format === "png" ? undefined : 1.0;
      const dataUrl = canvas.toDataURL(mimeType, quality);
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = `${base}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      return { format };
    },
    onMutate: () => {
      setPsdExportError(null);
      setPsdExportNotice(null);
    },
    onSuccess: (result) => {
      setPsdExportNotice(`Exported ${result.format.toUpperCase()} successfully.`);
    },
    onError: (err, format) => {
      console.error(`[export] failed format=${format}:`, err);
      setPsdExportError(
        err instanceof Error ? err.message : "Failed to export image.",
      );
    },
  });

  // -- Memos for child props -----------------------------------------------
  const chapterOptions = useMemo(
    () =>
      chapters.map((c) => ({
        id: c.id,
        title: c.title,
        chapter_number: c.chapter_number,
      })),
    [chapters],
  );

  const bottomBarPages = useMemo(
    () =>
      pages.map((p) => ({
        id: p.id,
        page_number: p.page_number,
        thumbnail_url: p.original_file_url
          ? toAbsoluteApiUrl(p.original_file_url)
          : null,
      })),
    [pages],
  );

  // -- Render branches -----------------------------------------------------
  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-brand-surface-bg text-brand-text-muted">
        Loading editor...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-4 bg-brand-surface-bg text-brand-text-muted">
        <p>{error}</p>
        <button
          onClick={() => navigate("/dashboard")}
          className="rounded-full border border-brand-border bg-white px-4 py-2 text-sm font-semibold"
        >
          Back to dashboard
        </button>
      </div>
    );
  }

  return (
    <div
      className="relative flex h-full w-full overflow-hidden bg-brand-bg font-sans text-brand-text"
      {...dragHandlers}
    >
      <div className="relative grid h-full w-full grid-cols-[minmax(0,1fr)_320px] overflow-hidden bg-brand-bg xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="relative grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)_auto] h-full">
          <TopHeader
            onUploadPages={(files) => void uploadPagesToActiveChapter(files)}
            isUploadingPages={isUploadingPages}
            uploadError={uploadError}
            uploadNotice={uploadNotice}
            onExportPsd={() => exportPsdMutation.mutate()}
            isExportingPsd={exportPsdMutation.isPending}
            onExportImage={(format) => exportImageMutation.mutate(format)}
            isExportingImage={exportImageMutation.isPending}
            exportError={psdExportError}
            exportNotice={psdExportNotice}
            // Workflow Bar Props merged in
            chapters={chapterOptions}
            activeChapterId={activeChapterId}
            onChapterChange={(id) => void handleChapterChange(id)}
            onCreateChapter={openCreateModal}
            isCreatingChapter={createChapterMutation.isPending}
            onRunMaskInference={() =>
              void maskEditor.workflow.runMaskInference()
            }
            isRunningMaskInference={maskEditor.workflow.isRunningMaskInference}
            onRunOCR={() =>
              void maskEditor.workflow.runOCR()
             }
            isRuningOCR = {maskEditor.workflow.isRunningOCR}
            allowRunOCR={hasMaskRegions}
            
            allowRunInpaint={hasOCRTexts}
            onRunInpaint={() => void maskEditor.workflow.runInpaint()}
            isRunningInpaint={maskEditor.workflow.isRuningInpaint}
            allowRunTranslate={hasInpaintedImage}
            onRunTranslate={async () => {
              const saved = await flushPendingSaves();
              if (!saved) return;
              await maskEditor.workflow.runTranslate();
            }}
            isRunningTranslate={maskEditor.workflow.isRunningTranslate}
            inpaintSettings={inpaintSettings}
            onInpaintSettingsChange={setInpaintSettings}
            translationSettings={translationSettings}
            onTranslationSettingsChange={setTranslationSettings}
            onSaveMasks={() => void maskEditor.workflow.saveMasks()}
            isSavingMasks={maskEditor.workflow.isSavingMasks}
            hasDirtyMasks={maskEditor.workflow.hasDirtyMasks}
            jobPhase={maskEditor.workflow.jobPhase}
            jobDetail={maskEditor.workflow.jobDetail}
          />

          <Workspace
            imageUrl={workspaceImageUrl}
            isInpaintedView={viewMode === "Translated" && Boolean(inpaintedImageUrl)}
            pageId={pageId}
            maskController={maskEditor.workspace}
            selectedTextRegionId={selectedTextRegionId}
            onTextRegionSelect={(regionId) => {
              setSelectedTextRegionId(regionId);
              maskEditor.workspace.setActiveMaskId(regionId);
            }}
            readingOrderLabelsByRegionId={readingOrderLabelsByRegionId}
            texts={texts}
            showTranslatedText={viewMode === "Translated"}
            textScaleByTextId={textScaleByTextId}
            onTextRegionManualPlacement={(regionId) => {
              if (!pageId) return;
              setTextPlacementMode(pageId, regionId, "manual");
            }}
            onRenderBoundsChange={handleRenderBoundsChange}
            onInpaintedImageSaved={async () => {
              if (pageId) await refreshPageDetail(pageId);
            }}
          />

          <BottomBar
            pages={bottomBarPages}
            currentPageId={pageId}
            onPageSelect={handlePageSelect}
          />
        </div>

        {/* Right Sidebar */}
        <RightSidebar
          items={ocrSidebarItems}
          activeWorkflow={activeWorkflow}
          onTextChange={
            viewMode === "Translated"
              ? handleTranslatedTextChange
              : handleTextChange
          }
          viewMode={viewMode}
          textScaleByTextId={textScaleByTextId}
          onTextScaleChange={handleTextScaleChange}
          textColorByTextId={textColorByTextId}
          defaultTextColor="#111111"
          onTextColorChange={handleTextColorChange}
          textFontByTextId={textFontByTextId}
          defaultTextFont={'"Komika Text", "Comic Sans MS", "Trebuchet MS", sans-serif'}
          onTextFontChange={handleTextFontChange}
          textFontWeightByTextId={textFontWeightByTextId}
          defaultTextFontWeight="normal"
          onTextFontWeightChange={handleTextFontWeightChange}
          placementModeByRegionId={placementModeByRegionId}
          onResetLayout={(textId, regionId) => {
            if (!pageId) return;
            clearTextOffset(pageId, textId);
            clearTextBoxSize(pageId, textId);
            setTextPlacementMode(pageId, regionId, "auto");
          }}
          selectedRegionId={selectedTextRegionId}
          onSelectRegion={(regionId) => {
            setSelectedTextRegionId(regionId);
            maskEditor.workspace.setActiveMaskId(regionId);
          }}
          saveState={saveState}
        />
      </div>

      <CreateChapterModal
        isOpen={isCreateModalOpen}
        description="Create chapter, then continue directly to upload pages."
        chapterTitle={newChapterTitle}
        onChapterTitleChange={setNewChapterTitle}
        chapterNumber={newChapterNumber}
        onChapterNumberChange={setNewChapterNumber}
        onClose={closeCreateModal}
        onSubmit={() => void createChapterMutation.mutate()}
        isSubmitting={createChapterMutation.isPending}
        submitLabel="Create & Upload"
      />

      {isDragActive ? (
        <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-black/20 backdrop-blur-[1px]">
          <div className="rounded-2xl border-2 border-dashed border-brand-border-gold bg-white px-8 py-6 text-center shadow-xl">
            <p className="text-[16px] font-semibold text-gray-900">
              Drop pages to upload
            </p>
            <p className="mt-1 text-[12px] text-gray-600">PNG, JPG, WEBP</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
