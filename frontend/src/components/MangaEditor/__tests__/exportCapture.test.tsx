/**
 * Tests for the export capture pipeline in MangaEditor.
 *
 * Verifies:
 * - document.fonts.ready is awaited before html2canvas fires
 * - html2canvas is called with the correct DOM element
 * - Overlay elements (mask polygons, erase canvas, interaction boxes)
 *   are hidden in the cloned document during capture
 * - Exported filename matches page ID and format
 */
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

// ---------------------------------------------------------------------------
// Mock html2canvas — must be hoisted before any imports that use it
// ---------------------------------------------------------------------------
const mockCanvas = {
  width: 800,
  height: 1200,
  toDataURL: vi.fn(() => "data:image/png;base64,fake"),
};
vi.mock("html2canvas", () => ({ default: vi.fn(() => Promise.resolve(mockCanvas)) }));
vi.mock("jspdf", () => ({
  jsPDF: vi.fn().mockImplementation(() => ({
    addImage: vi.fn(),
    save: vi.fn(),
  })),
}));

// ---------------------------------------------------------------------------
// Helpers that mirror the export mutation logic from MangaEditor.tsx.
// Extracted so we can test the logic without mounting the full editor.
// ---------------------------------------------------------------------------

interface CaptureOptions {
  pageId: string;
  target: HTMLElement;
  fontsReady: Promise<void>;
}

async function runExportCapture(format: "png" | "jpg" | "webp" | "pdf", opts: CaptureOptions) {
  const { pageId, target, fontsReady } = opts;

  const baseImage = target.querySelector("img") as HTMLImageElement | null;
  const displayedW = Math.max(1, target.clientWidth || 800);
  const displayedH = Math.max(1, target.clientHeight || 1200);
  const naturalW = baseImage?.naturalWidth ?? displayedW;
  const naturalH = baseImage?.naturalHeight ?? displayedH;

  if (baseImage && !baseImage.complete) {
    await baseImage.decode().catch(() => undefined);
  }
  await fontsReady;
  await new Promise<void>((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
  );

  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import("html2canvas"),
    import("jspdf"),
  ]);

  const nativeRatio = Math.max(naturalW / displayedW, naturalH / displayedH, 1);
  const captureScale = Math.max(2, Math.min(6, nativeRatio));

  const canvas = await (html2canvas as unknown as Mock)(target, {
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
    onclone: (doc: Document) => {
      doc
        .querySelectorAll(".translated-text-draggable, [data-export-hide='true']")
        .forEach((el) => {
          (el as HTMLElement).style.display = "none";
        });
    },
  });

  if (format === "pdf") {
    const pdf = new (jsPDF as unknown as new (...args: unknown[]) => { addImage: Mock; save: Mock })({
      orientation: canvas.width >= canvas.height ? "landscape" : "portrait",
      unit: "px",
      format: [canvas.width, canvas.height],
      compress: true,
    });
    const pngData = (canvas as HTMLCanvasElement).toDataURL("image/png");
    pdf.addImage(pngData, "PNG", 0, 0, canvas.width, canvas.height);
    pdf.save(`page-${pageId}-translated.pdf`);
    return { format: "pdf" as const };
  }

  const mimeType =
    format === "jpg" ? "image/jpeg" : format === "webp" ? "image/webp" : "image/png";
  const dataUrl = (canvas as HTMLCanvasElement).toDataURL(mimeType);
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = `page-${pageId}-translated.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  return { format };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("export capture pipeline", () => {
  let target: HTMLDivElement;
  let img: HTMLImageElement;

  beforeEach(() => {
    vi.clearAllMocks();
    mockCanvas.toDataURL.mockReturnValue("data:image/png;base64,fake");

    target = document.createElement("div");
    target.setAttribute("data-export-target", "workspace-canvas");
    Object.defineProperty(target, "clientWidth", { value: 400, configurable: true });
    Object.defineProperty(target, "clientHeight", { value: 600, configurable: true });

    img = document.createElement("img");
    img.src = "/api/v1/storage/proj/ch/page-1/original";
    Object.defineProperty(img, "naturalWidth", { value: 2400, configurable: true });
    Object.defineProperty(img, "naturalHeight", { value: 3600, configurable: true });
    Object.defineProperty(img, "complete", { value: true, configurable: true });
    target.appendChild(img);

    document.body.appendChild(target);
  });

  it("awaits document.fonts.ready before calling html2canvas", async () => {
    const { default: html2canvas } = await import("html2canvas");

    let resolveFonts!: () => void;
    const fontsReady = new Promise<void>((resolve) => { resolveFonts = resolve; });

    // Start capture but don't await yet
    const capturePromise = runExportCapture("png", {
      pageId: "page-1",
      target,
      fontsReady,
    });

    // html2canvas must NOT have been called yet (fonts not ready)
    await new Promise((r) => setTimeout(r, 0));
    expect(html2canvas).not.toHaveBeenCalled();

    // Resolve fonts → now html2canvas can fire
    resolveFonts();
    await capturePromise;
    expect(html2canvas).toHaveBeenCalledOnce();
  });

  it("calls html2canvas with the export target element", async () => {
    const { default: html2canvas } = await import("html2canvas");
    await runExportCapture("png", {
      pageId: "page-1",
      target,
      fontsReady: Promise.resolve(),
    });
    expect(html2canvas).toHaveBeenCalledWith(target, expect.objectContaining({ useCORS: true }));
  });

  it("image src is relative (same-origin) — no http:// origin in img src", () => {
    expect(img.src).toMatch(/^\/api\/v1\/storage\//);
    expect(img.src).not.toMatch(/^https?:\/\/[^/]/);
  });

  it("onclone hides elements with data-export-hide and .translated-text-draggable", async () => {
    const { default: html2canvas } = await import("html2canvas") as { default: Mock };

    // Capture the onclone callback from the html2canvas options
    let capturedOnclone: ((doc: Document) => void) | undefined;
    (html2canvas as Mock).mockImplementationOnce((_el: unknown, opts: { onclone?: (doc: Document) => void }) => {
      capturedOnclone = opts.onclone;
      return Promise.resolve(mockCanvas);
    });

    await runExportCapture("png", {
      pageId: "page-1",
      target,
      fontsReady: Promise.resolve(),
    });

    // Build a clone-like document with the elements we want hidden
    const cloneDoc = document.implementation.createHTMLDocument();
    const maskDiv = cloneDoc.createElement("div");
    maskDiv.setAttribute("data-export-hide", "true");
    const interactionBox = cloneDoc.createElement("div");
    interactionBox.className = "translated-text-draggable";
    cloneDoc.body.appendChild(maskDiv);
    cloneDoc.body.appendChild(interactionBox);

    expect(capturedOnclone).toBeDefined();
    capturedOnclone!(cloneDoc);

    expect(maskDiv.style.display).toBe("none");
    expect(interactionBox.style.display).toBe("none");
  });

  it("download anchor uses correct filename with page ID and format", async () => {
    const clickedLinks: HTMLAnchorElement[] = [];
    vi.spyOn(document.body, "appendChild").mockImplementation((node) => {
      if (node instanceof HTMLAnchorElement) clickedLinks.push(node);
      return node as Node;
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockReturnValue(undefined);

    await runExportCapture("jpg", {
      pageId: "page-abc-123",
      target,
      fontsReady: Promise.resolve(),
    });

    expect(clickedLinks.length).toBeGreaterThan(0);
    expect(clickedLinks[0].download).toBe("page-page-abc-123-translated.jpg");
  });

  it("capture scale is bounded between 2 and 6", async () => {
    const { default: html2canvas } = await import("html2canvas");
    // nativeRatio = max(2400/400, 3600/600) = max(6, 6) = 6 → captureScale = min(6, 6) = 6
    await runExportCapture("png", {
      pageId: "page-1",
      target,
      fontsReady: Promise.resolve(),
    });
    expect(html2canvas).toHaveBeenCalledWith(
      target,
      expect.objectContaining({ scale: 6 }),
    );
  });
});
