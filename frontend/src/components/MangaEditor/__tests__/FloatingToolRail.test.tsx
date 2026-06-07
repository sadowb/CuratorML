import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import FloatingToolRail from "../FloatingToolRail";
import type { WorkspaceMaskController } from "../../../hooks/editor/maskEditorTypes";

function createMaskController(): WorkspaceMaskController {
  return {
    pageId: "page-1",
    activeTool: "select",
    setActiveTool: vi.fn(),
    showMasks: true,
    toggleShowMasks: vi.fn(),
    showLabels: true,
    toggleShowLabels: vi.fn(),
    filter: { mode: "all" },
    availableRegionKinds: [],
    setFilterAll: vi.fn(),
    setFilterByKind: vi.fn(),
    activeMaskId: null,
    setActiveMaskId: vi.fn(),
    regions: [],
    allRegions: [],
    editablePolygonsByRegionId: {},
    maskError: null,
    onRegionPolygonChange: vi.fn(),
    onRegionDelete: vi.fn(),
    onRegionCreate: vi.fn(),
    penShape: null,
    setPenShape: vi.fn(),
    penTarget: "balloon" as const,
    setPenTarget: vi.fn(),
    globalTextStyle: {
      color: "#111111",
      fontFamily: "Arial, sans-serif",
      fontSize: "md" as const,
      fontWeight: "normal" as const,
      textAlign: "center" as const,
    },
    textStylesByRegionId: {},
    setTextStyle: vi.fn(),
  };
}

function renderRail(activeTool: "select" | "eraser" | "pen") {
  function Harness() {
    const [penShape, setPenShape] =
      useState<WorkspaceMaskController["penShape"]>(null);
    const [penTarget, setPenTarget] =
      useState<WorkspaceMaskController["penTarget"]>("balloon");
    const maskController: WorkspaceMaskController = {
      ...createMaskController(),
      penShape,
      setPenShape: (shape) => setPenShape(shape),
      penTarget,
      setPenTarget,
    };

    return (
      <FloatingToolRail
        zoomLevel={100}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
        activeTool={activeTool}
        onToolChange={vi.fn()}
        maskController={maskController}
      />
    );
  }

  return render(<Harness />);
}

function renderStaticRail(activeTool: "select" | "eraser" | "pen") {
  return render(
    <FloatingToolRail
      zoomLevel={100}
      onZoomIn={vi.fn()}
      onZoomOut={vi.fn()}
      activeTool={activeTool}
      onToolChange={vi.fn()}
      maskController={createMaskController()}
    />,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FloatingToolRail", () => {
  it("does not render the pen flyout when pen tool is inactive", () => {
    renderStaticRail("select");
    expect(screen.queryByRole("group", { name: "Pen tool options" })).not.toBeInTheDocument();
  });

  it("renders pen flyout and keeps step 2 disabled until shape selection", () => {
    renderRail("pen");

    const panelButton = screen.getByRole("button", { name: "Panel" });
    const balloonButton = screen.getByRole("button", { name: "Balloon" });
    const textButton = screen.getByRole("button", { name: "Text" });

    expect(panelButton).toBeDisabled();
    expect(balloonButton).toBeDisabled();
    expect(textButton).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Box" }));

    expect(panelButton).not.toBeDisabled();
    expect(balloonButton).not.toBeDisabled();
    expect(textButton).not.toBeDisabled();

    fireEvent.click(panelButton);
    expect(panelButton).toHaveAttribute("aria-pressed", "true");
  });

  it("opens flyout on the right when there is not enough room on the left", () => {
    const originalInnerWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: 1200,
    });

    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      x: 0,
      y: 0,
      width: 72,
      height: 340,
      top: 0,
      right: 82,
      bottom: 340,
      left: 10,
      toJSON: () => ({}),
    } as DOMRect);

    renderRail("pen");
    const flyout = screen.getByRole("group", { name: "Pen tool options" });

    // Since it falls back to the right, it uses left-[84px] to position to the right
    expect(flyout.className).toContain("left-[84px]");
    expect(flyout.className).not.toContain("right-[84px]");

    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: originalInnerWidth,
    });
  });

  it("toggles flyout visibility when clicking the active pen button", () => {
    const onToolChange = vi.fn();
    render(
      <FloatingToolRail
        zoomLevel={100}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
        activeTool="pen"
        onToolChange={onToolChange}
        maskController={createMaskController()}
      />,
    );

    // Should be visible initially because activeTool="pen"
    expect(screen.getByRole("group", { name: "Pen tool options" })).toBeInTheDocument();

    const penButton = screen.getByRole("button", { name: "Pen tool" });

    // Click to hide
    fireEvent.click(penButton);
    expect(screen.queryByRole("group", { name: "Pen tool options" })).not.toBeInTheDocument();
    expect(onToolChange).not.toHaveBeenCalled();

    // Click to show
    fireEvent.click(penButton);
    expect(screen.getByRole("group", { name: "Pen tool options" })).toBeInTheDocument();
  });
});
