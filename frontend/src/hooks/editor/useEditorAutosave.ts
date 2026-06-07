import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { patchPageText } from "../../lib/api";
import type { PageText, PageTextPatchPayload } from "../../types/api";

type SaveState = "idle" | "dirty" | "saving" | "saved" | "error";

interface UseEditorAutosaveParams {
  pageId?: string;
  setTexts: Dispatch<SetStateAction<PageText[]>>;
  upsertDraft: (
    pageId: string,
    textId: string,
    draft: PageTextPatchPayload,
  ) => void;
  clearDraft: (pageId: string, textId: string) => void;
}

export function useEditorAutosave({
  pageId,
  setTexts,
  upsertDraft,
  clearDraft,
}: UseEditorAutosaveParams) {
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [dirtyPatchesByTextId, setDirtyPatchesByTextId] = useState<
    Record<string, PageTextPatchPayload>
  >({});

  const saveTimerRef = useRef<number | null>(null);
  const isSavingRef = useRef(false);
  const dirtyRef = useRef<Record<string, PageTextPatchPayload>>({});

  useEffect(() => {
    dirtyRef.current = dirtyPatchesByTextId;
  }, [dirtyPatchesByTextId]);

  const saveDirtyNow = useCallback(async (): Promise<boolean> => {
    if (!pageId) return true;
    if (isSavingRef.current) return false;

    const snapshot = dirtyRef.current;
    const idsToSave = Object.keys(snapshot);
    if (idsToSave.length === 0) return true;

    isSavingRef.current = true;
    setSaveState("saving");

    const succeeded: string[] = [];
    let hasFailure = false;

    for (const textId of idsToSave) {
      const patchPayload = snapshot[textId];
      if (!patchPayload) continue;
      try {
        await patchPageText(pageId, textId, patchPayload);
        clearDraft(pageId, textId);
        succeeded.push(textId);
      } catch {
        hasFailure = true;
      }
    }

    setDirtyPatchesByTextId((prev) => {
      if (succeeded.length === 0) return prev;
      const next = { ...prev };
      for (const id of succeeded) delete next[id];
      return next;
    });

    setSaveState(hasFailure ? "error" : "saved");
    if (!hasFailure) {
      window.setTimeout(
        () => setSaveState((state) => (state === "saved" ? "idle" : state)),
        1500,
      );
    }
    isSavingRef.current = false;
    return !hasFailure;
  }, [clearDraft, pageId]);

  useEffect(() => {
    if (!pageId) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (
        saveState === "saving" ||
        Object.keys(dirtyPatchesByTextId).length > 0
      ) {
        event.preventDefault();
        event.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirtyPatchesByTextId, pageId, saveState]);

  useEffect(() => {
    const dirtyTextIds = Object.keys(dirtyPatchesByTextId);
    if (!pageId || dirtyTextIds.length === 0) {
      return;
    }

    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = window.setTimeout(async () => {
      await saveDirtyNow();
    }, 1500);

    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, [dirtyPatchesByTextId, pageId, saveDirtyNow]);

  const queueDraftPatch = (textId: string, patch: PageTextPatchPayload) => {
    if (!pageId) {
      return;
    }

    setDirtyPatchesByTextId((prev) => ({
      ...prev,
      [textId]: {
        ...(prev[textId] ?? {}),
        ...patch,
      },
    }));
    upsertDraft(pageId, textId, patch);
    setSaveState("dirty");
  };

  const handleTextChange = (textId: string, value: string) => {
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId ? { ...text, ocr_text_corrected: value } : text,
      ),
    );
    queueDraftPatch(textId, { ocr_text_corrected: value });
  };

  const handleTranslatedTextChange = (textId: string, value: string) => {
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId
          ? {
              ...text,
              display_text_final: value,
              translation_corrected: value,
            }
          : text,
      ),
    );
    queueDraftPatch(textId, {
      display_text_final: value,
      translation_corrected: value,
    });
  };

  const handleTextScaleChange = (textId: string, scale: number) => {
    const clamped = Math.min(Math.max(scale, 0.6), 2);
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId
          ? {
              ...text,
              render_scale: clamped,
            }
          : text,
      ),
    );
    queueDraftPatch(textId, { render_scale: clamped });
  };

  const handleTextColorChange = (textId: string, color: string) => {
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId
          ? {
              ...text,
              render_color: color,
            }
          : text,
      ),
    );
    queueDraftPatch(textId, { render_color: color });
  };

  const handleTextFontChange = (textId: string, fontFamily: string) => {
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId
          ? {
              ...text,
              render_font_family: fontFamily,
            }
          : text,
      ),
    );
    queueDraftPatch(textId, { render_font_family: fontFamily });
  };

  const handleTextFontWeightChange = (textId: string, fontWeight: "normal" | "bold") => {
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId
          ? {
              ...text,
              render_font_weight: fontWeight,
            }
          : text,
      ),
    );
    queueDraftPatch(textId, { render_font_weight: fontWeight });
  };

  const handleRenderBoundsChange = (textId: string, bounds: [number, number, number, number]) => {
    setTexts((prev) =>
      prev.map((text) =>
        text.id === textId
          ? {
              ...text,
              render_bounds: bounds,
            }
          : text,
      ),
    );
    queueDraftPatch(textId, { render_bounds: bounds });
  };

  return {
    saveState,
    dirtyTextIds: Object.keys(dirtyPatchesByTextId),
    handleTextChange,
    handleTranslatedTextChange,
    handleTextScaleChange,
    handleTextColorChange,
    handleTextFontChange,
    handleTextFontWeightChange,
    handleRenderBoundsChange,
    flushPendingSaves: saveDirtyNow,
    setSaveState,
  };
}
