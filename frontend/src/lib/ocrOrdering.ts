import type { PageRegion, PageText } from "../types/api";

export interface OrderedOcrItem {
  text: PageText;
  title: string;
  orderLabel: string;
}

function getRegionCenter(region: PageRegion | undefined): { x: number | null; y: number | null } {
  if (!region || !Array.isArray(region.bbox_json) || region.bbox_json.length !== 4) {
    return { x: null, y: null };
  }
  const [x1, y1, x2, y2] = region.bbox_json;
  return { x: (x1 + x2) / 2, y: (y1 + y2) / 2 };
}

function getTextReadingOrder(
  text: PageText,
  regionById: Map<string, PageRegion>,
): {
  panelOrder: number | null;
  bubbleOrder: number | null;
  itemOrder: number | null;
  x: number | null;
  y: number | null;
} {
  const region = regionById.get(text.region_id);
  if (!region) {
    return {
      panelOrder: null,
      bubbleOrder: null,
      itemOrder: null,
      x: null,
      y: null,
    };
  }

  const center = getRegionCenter(region);
  const itemOrder = region.reading_order ?? null;
  let parent = region.parent_region_id
    ? regionById.get(region.parent_region_id)
    : null;

  let panelOrder: number | null = null;
  let bubbleOrder: number | null = null;

  if (parent && parent.region_kind === "balloon") {
    bubbleOrder = parent.reading_order ?? null;
    parent = parent.parent_region_id ? regionById.get(parent.parent_region_id) : null;
  }
  
  if (parent && parent.region_kind === "panel") {
    panelOrder = parent.reading_order ?? null;
  }

  return {
    panelOrder,
    bubbleOrder,
    itemOrder,
    x: center.x,
    y: center.y,
  };
}

export function buildOrderedOcrItems(
  texts: PageText[],
  regions: PageRegion[],
  readingDirection: "LTR" | "RTL" = "LTR",
): OrderedOcrItem[] {
  const compareX = (left: number | null, right: number | null): number => {
    const l = left ?? 0;
    const r = right ?? 0;
    if (l === r) return 0;
    return readingDirection === "RTL" ? r - l : l - r;
  };

  const regionById = new Map(regions.map((region) => [region.id, region]));
  const sortedTexts = [...texts].sort((left, right) => {
    const leftOrder = getTextReadingOrder(left, regionById);
    const rightOrder = getTextReadingOrder(right, regionById);

    if ((leftOrder.panelOrder === null) !== (rightOrder.panelOrder === null)) {
      return leftOrder.panelOrder === null ? 1 : -1;
    }
    if ((leftOrder.panelOrder ?? 0) !== (rightOrder.panelOrder ?? 0)) {
      return (leftOrder.panelOrder ?? 0) - (rightOrder.panelOrder ?? 0);
    }

    if ((leftOrder.bubbleOrder === null) !== (rightOrder.bubbleOrder === null)) {
      return leftOrder.bubbleOrder === null ? 1 : -1;
    }
    if ((leftOrder.bubbleOrder ?? 0) !== (rightOrder.bubbleOrder ?? 0)) {
      return (leftOrder.bubbleOrder ?? 0) - (rightOrder.bubbleOrder ?? 0);
    }

    if ((leftOrder.itemOrder === null) !== (rightOrder.itemOrder === null)) {
      return leftOrder.itemOrder === null ? 1 : -1;
    }
    if ((leftOrder.itemOrder ?? 0) !== (rightOrder.itemOrder ?? 0)) {
      return (leftOrder.itemOrder ?? 0) - (rightOrder.itemOrder ?? 0);
    }

    // Fallback: If regions lack proper reading order tags, order by X/Y
    // primary axis follows reading direction (RTL: right->left, LTR: left->right),
    // then vertical top->bottom.
    if ((leftOrder.x ?? 0) !== (rightOrder.x ?? 0)) {
      return compareX(leftOrder.x, rightOrder.x);
    }
    if ((leftOrder.y ?? 0) !== (rightOrder.y ?? 0)) {
      return (leftOrder.y ?? 0) - (rightOrder.y ?? 0);
    }
    if (left.created_at !== right.created_at) {
      return left.created_at.localeCompare(right.created_at);
    }
    return left.id.localeCompare(right.id);
  });

  return sortedTexts.map((text, index) => {
    const { panelOrder, bubbleOrder, itemOrder } = getTextReadingOrder(text, regionById);
    let orderLabel = `U-${itemOrder ?? index + 1}`;
    
    if (panelOrder !== null) {
      if (bubbleOrder !== null) {
         orderLabel = `P${panelOrder}-B${bubbleOrder}-${itemOrder}`;
      } else if (itemOrder !== null) {
         orderLabel = `P${panelOrder}-${itemOrder}`;
      }
    }
    
    return {
      text,
      title: `${String(index + 1).padStart(2, "0")} · OCR Block`,
      orderLabel,
    };
  });
}

export function buildReadingOrderLabelsByRegionId(
  items: OrderedOcrItem[],
): Record<string, string> {
  return Object.fromEntries(
    items.map(({ text, orderLabel }) => [text.region_id, orderLabel]),
  );
}
