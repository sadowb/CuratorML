import { useState, useEffect, useCallback, useMemo } from "react";
import type { PageRegion } from "../../types/api";
import type {
  EditorTool,
  MaskRegionFilter,
  TypographyStyle
} from "./maskEditorTypes";
import {
  isEditablePolygon,
  buildEditableMap,
  applyFilter,
  bboxToPolygon,
  deriveBbox
} from "./utils/maskGeometry";

const DEFAULT_STYLE: TypographyStyle = {
  color: "#111111",
  fontFamily: "\"Komika Text\", \"Comic Sans MS\", \"Trebuchet MS\", sans-serif",
  fontSize: "md",
  fontWeight: "normal",
  textAlign: "center",
};

function normalizeStyle(style: Partial<TypographyStyle> | null | undefined): TypographyStyle {
  return { ...DEFAULT_STYLE, ...(style ?? {}) };
}

export function useMaskStore(initialRegions: PageRegion[], pageId?: string) {
  // -- Workspace UI state --------------------------------------------------
  const [activeTool, setActiveTool] = useState<EditorTool>("select");
  const [showMasks, setShowMasks] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [filter, setFilter] = useState<MaskRegionFilter>({ mode: "all" });
  const [activeMaskId, setActiveMaskId] = useState<string | null>(null);

  // -- Pen Settings --------------------------------------------------------
  const [penShape, setPenShape] = useState<"box" | "polygon">("box");
  const [penTarget, setPenTarget] = useState<"panel" | "balloon" | "text">("balloon");

  // -- Mask tracking state -------------------------------------------------
  const [createdRegions, setCreatedRegions] = useState<PageRegion[]>([]);
  const [dirtyIds, setDirtyIds] = useState<Set<string>>(new Set());
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());
  const [editablePolygonsByRegionId, setEditablePolygons] = useState<Record<string, number[][]>>({});

  // -- Typography state ----------------------------------------------------
  const [globalTextStyle, setGlobalTextStyle] = useState<TypographyStyle>(() => {
    try {
      const cached = localStorage.getItem("manga_editor_global_style");
      return cached ? normalizeStyle(JSON.parse(cached)) : DEFAULT_STYLE;
    } catch { return DEFAULT_STYLE; }
  });

  const [textStylesByRegionId, setTextStyles] = useState<Record<string, TypographyStyle>>(() => {
    try {
      const cached = localStorage.getItem("manga_editor_region_styles");
      if (!cached) return {};
      const parsed = JSON.parse(cached) as Record<string, Partial<TypographyStyle>>;
      return Object.fromEntries(
        Object.entries(parsed).map(([regionId, style]) => [regionId, normalizeStyle(style)]),
      );
    } catch { return {}; }
  });

  // -- Sync styles ---------------------------------------------------------
  useEffect(() => {
    localStorage.setItem("manga_editor_global_style", JSON.stringify(globalTextStyle));
  }, [globalTextStyle]);

  useEffect(() => {
    localStorage.setItem("manga_editor_region_styles", JSON.stringify(textStylesByRegionId));
  }, [textStylesByRegionId]);

  // -- Derived Regions -----------------------------------------------------
  const editableRegions = useMemo(() =>
    [...initialRegions, ...createdRegions].filter((r) => {
      if (!r.is_active) return false;
      if (r.region_kind === "text") {
        return isEditablePolygon(r.polygon_json) || isEditablePolygon(bboxToPolygon(r.bbox_json));
      }
      // Keep panel/balloon regions available even when only bbox is valid.
      // Otherwise text→balloon association can fail because the balloon is absent from allRegions.
      return isEditablePolygon(r.polygon_json) || isEditablePolygon(bboxToPolygon(r.bbox_json));
    }),
    [initialRegions, createdRegions]
  );

  const maskRegions = useMemo(() => {
    return editableRegions
      .map((region) => {
        if (deletedIds.has(region.id)) return { ...region, is_active: false };
        if (!dirtyIds.has(region.id)) return region;

        const edited = editablePolygonsByRegionId[region.id];
        if (!isEditablePolygon(edited)) return region;

        if (region.region_kind === "text") {
          return { 
            ...region, 
            bbox_json: deriveBbox(edited), 
            polygon_json: edited, // Ensure polygon is saved for text too
            confidence: 1.0      // Mark as manual precision
          };
        }
        return { 
          ...region, 
          polygon_json: edited, 
          bbox_json: deriveBbox(edited),
          confidence: 1.0      // Mark as manual precision
        };
      })
      .filter((r) => r.is_active);
  }, [deletedIds, dirtyIds, editableRegions, editablePolygonsByRegionId]);

  const filteredRegions = useMemo(
    () => applyFilter(maskRegions, filter),
    [maskRegions, filter]
  );

  const availableRegionKinds = useMemo(
    () => Array.from(new Set(editableRegions.map((r) => r.region_kind))).sort(),
    [editableRegions]
  );

  // -- Handlers ------------------------------------------------------------
  const reset = useCallback(() => {
    setEditablePolygons({});
    setDirtyIds(new Set());
    setDeletedIds(new Set());
    setCreatedRegions([]);
    setActiveTool("select");
    setShowMasks(true);
    setShowLabels(true);
    setFilter({ mode: "all" });
    setActiveMaskId(null);
  }, []);

  // Sync editable polygons when regions change
  useEffect(() => {
    setEditablePolygons(buildEditableMap(editableRegions));

    // PRESERVE temp IDs (Fix for "must move to save" bug)
    setDirtyIds((prev) => {
      const next = new Set<string>();
      prev.forEach(id => { if (id.startsWith("temp-")) next.add(id); });
      return next;
    });
    setDeletedIds((prev) => {
      const next = new Set<string>();
      prev.forEach(id => { if (id.startsWith("temp-")) next.add(id); });
      return next;
    });
  }, [editableRegions]);

  return {
    state: {
      activeTool,
      showMasks,
      showLabels,
      filter,
      activeMaskId,
      createdRegions,
      dirtyIds,
      deletedIds,
      editablePolygonsByRegionId,
      globalTextStyle,
      textStylesByRegionId,
      editableRegions,
      filteredRegions,
      maskRegions,
      availableRegionKinds,
      penShape,
      penTarget,
    },
    actions: {
      setActiveTool,
      setShowMasks,
      setShowLabels,
      setFilter,
      setActiveMaskId,
      setCreatedRegions,
      setDirtyIds,
      setDeletedIds,
      setEditablePolygons,
      setGlobalTextStyle,
      setTextStyles,
      setPenShape,
      setPenTarget,
      reset,

      handleRegionPolygonChange: (regionId: string, polygon: number[][]) => {
        if (polygon.length < 3) return;
        setEditablePolygons((prev) => ({ ...prev, [regionId]: polygon }));
        setDirtyIds((prev) => new Set(prev).add(regionId));
        setDeletedIds((prev) => {
          if (!prev.has(regionId)) return prev;
          const next = new Set(prev);
          next.delete(regionId);
          return next;
        });
      },

      handleRegionDelete: (regionId: string) => {
        setDeletedIds((prev) => new Set(prev).add(regionId));
        setDirtyIds((prev) => {
          if (!prev.has(regionId)) return prev;
          const next = new Set(prev);
          next.delete(regionId);
          return next;
        });
      },

      handleRegionCreate: (kind: string, polygon: number[][]) => {
        if (polygon.length < 3) return;
        const regionId = `temp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const newRegion: PageRegion = {
          id: regionId,
          page_id: pageId || "",
          parent_region_id: null,
          pipeline_run_id: null,
          created_by_user_id: null,
          region_kind: kind,
          polygon_json: polygon,
          bbox_json: deriveBbox(polygon),
          reading_order: null,
          origin: "user_edited",
          is_active: true,
          confidence: 1.0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setCreatedRegions((prev) => [...prev, newRegion]);
        setDirtyIds((prev) => new Set(prev).add(regionId));
        setActiveMaskId(regionId);
      },

      handleSetTextStyle: (style: Partial<TypographyStyle>) => {
        if (activeMaskId) {
          setTextStyles((prev) => ({
            ...prev,
            [activeMaskId]: { ...(prev[activeMaskId] || globalTextStyle), ...style },
          }));
        } else {
          setGlobalTextStyle((prev) => ({ ...prev, ...style }));
        }
      },
    },
  };
}
