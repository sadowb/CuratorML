import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import type { WorkspaceMaskController } from '../../../hooks/editor/maskEditorTypes';
import Workspace from '../Workspace';

const transformControls = {
  zoomIn: vi.fn(),
  zoomOut: vi.fn(),
};

let latestTransformWrapperProps: Record<string, unknown> | null = null;
let latestTransformComponentProps: Record<string, unknown> | null = null;
let currentScale = 1;

vi.mock('react-zoom-pan-pinch', async () => {
  const TransformWrapper = (props: Record<string, unknown>) => {
    latestTransformWrapperProps = props;
    return <div data-testid="transform-wrapper">{props.children as ReactNode}</div>;
  };

  return {
    TransformWrapper,
    TransformComponent: (props: Record<string, unknown>) => {
      latestTransformComponentProps = props;
      return <div data-testid="transform-component">{props.children as ReactNode}</div>;
    },
    useControls: () => transformControls,
    useTransformComponent: (selector: (state: { state: { scale: number } }) => number) =>
      selector({ state: { scale: currentScale } }),
  };
});

function createMaskController(overrides: Partial<WorkspaceMaskController> = {}): WorkspaceMaskController {
  return {
    activeTool: 'select',
    setActiveTool: vi.fn(),
    showMasks: true,
    toggleShowMasks: vi.fn(),
    showLabels: true,
    toggleShowLabels: vi.fn(),
    filter: { mode: 'all' },
    availableRegionKinds: ['text', 'panel'],
    setFilterAll: vi.fn(),
    setFilterByKind: vi.fn(),
    activeMaskId: null,
    setActiveMaskId: vi.fn(),
    regions: [
      {
        id: 'region-1',
        page_id: 'page-1',
        parent_region_id: null,
        pipeline_run_id: null,
        created_by_user_id: null,
        region_kind: 'text',
        polygon_json: [
          [10, 10],
          [60, 10],
          [60, 60],
        ],
        bbox_json: [10, 10, 60, 60],
        confidence: 0.9,
        reading_order: null,
        origin: 'manual',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ],
    allRegions: [
      {
        id: 'region-1',
        page_id: 'page-1',
        parent_region_id: null,
        pipeline_run_id: null,
        created_by_user_id: null,
        region_kind: 'text',
        polygon_json: [
          [10, 10],
          [60, 10],
          [60, 60],
        ],
        bbox_json: [10, 10, 60, 60],
        confidence: 0.9,
        reading_order: null,
        origin: 'manual',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ],
    editablePolygonsByRegionId: {
      'region-1': [
        [10, 10],
        [60, 10],
        [60, 60],
      ],
    },
    maskError: null,
    onRegionPolygonChange: vi.fn(),
    onRegionDelete: vi.fn(),
    onRegionCreate: vi.fn(),
    penShape: 'box',
    setPenShape: vi.fn(),
    penTarget: 'balloon',
    setPenTarget: vi.fn(),
    textStylesByRegionId: {},
    globalTextStyle: {
      color: '#111111',
      fontFamily: 'Arial, sans-serif',
      fontSize: 'md',
      fontWeight: 'normal',
      textAlign: 'center',
    },
    setTextStyle: vi.fn(),
    ...overrides,
  };
}

describe('Workspace zoom/pan integration', () => {
  beforeEach(() => {
    latestTransformWrapperProps = null;
    latestTransformComponentProps = null;
    currentScale = 1;
    transformControls.zoomIn.mockClear();
    transformControls.zoomOut.mockClear();
  });

  it('disables panning when tool is not select', () => {
    const selectController = createMaskController({ activeTool: 'select' });
    const { rerender } = render(<Workspace imageUrl="/page-a.png" maskController={selectController} />);

    expect((latestTransformWrapperProps?.panning as { disabled?: boolean }).disabled).toBe(false);

    const penController = createMaskController({ activeTool: 'pen' });
    rerender(<Workspace imageUrl="/page-a.png" maskController={penController} />);
    expect((latestTransformWrapperProps?.panning as { disabled?: boolean }).disabled).toBe(true);
  });

  it('uses transform scale for the zoom display', () => {
    currentScale = 1.37;
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    expect(screen.getByText('137%')).toBeInTheDocument();
  });

  it('wires mask visibility and kind filter controls', () => {
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    fireEvent.click(screen.getByRole('button', { name: 'Hide masks (1/1)' }));
    expect(controller.toggleShowMasks).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter masks by type' }), {
      target: { value: 'panel' },
    });
    expect(controller.setFilterByKind).toHaveBeenCalledWith('panel');
  });

  it('renders text regions from bbox geometry and balloon regions from polygon geometry', async () => {
    const controller = createMaskController({
      regions: [
        {
          id: 'region-text',
          page_id: 'page-1',
          parent_region_id: null,
          pipeline_run_id: null,
          created_by_user_id: null,
          region_kind: 'text',
          polygon_json: [
            [12, 12],
            [58, 18],
            [52, 54],
            [18, 52],
          ],
          bbox_json: [10, 10, 60, 60],
          confidence: 0.9,
          reading_order: null,
          origin: 'manual',
          is_active: true,
          created_at: '',
          updated_at: '',
        },
        {
          id: 'region-balloon',
          page_id: 'page-1',
          parent_region_id: null,
          pipeline_run_id: null,
          created_by_user_id: null,
          region_kind: 'balloon',
          polygon_json: [
            [100, 100],
            [150, 105],
            [145, 155],
            [110, 160],
          ],
          bbox_json: [95, 95, 155, 165],
          confidence: 0.9,
          reading_order: null,
          origin: 'manual',
          is_active: true,
          created_at: '',
          updated_at: '',
        },
      ],
      allRegions: [],
      editablePolygonsByRegionId: {},
    });

    const { container } = render(<Workspace imageUrl="/page-a.png" maskController={controller} />);
    const image = screen.getByAltText('Manga Page') as HTMLImageElement;

    Object.defineProperty(image, 'naturalWidth', { configurable: true, value: 1200 });
    Object.defineProperty(image, 'naturalHeight', { configurable: true, value: 1600 });
    fireEvent.load(image);

    await waitFor(() => {
      const polygons = container.querySelectorAll('polygon');
      expect(polygons).toHaveLength(2);
      expect(polygons[0]?.getAttribute('points')).toBe('10,10 60,10 60,60 10,60');
      expect(polygons[1]?.getAttribute('points')).toBe('100,100 150,105 145,155 110,160');
    });
  });

  it('renders reading-order badges for text regions when labels are provided', async () => {
    const controller = createMaskController();
    render(
      <Workspace
        imageUrl="/page-a.png"
        maskController={controller}
        readingOrderLabelsByRegionId={{ "region-1": "P1-2" }}
      />,
    );

    const image = screen.getByAltText("Manga Page") as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 1200 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 1600 });
    fireEvent.load(image);

    await waitFor(() => {
      expect(screen.getByText("P1-2")).toBeInTheDocument();
    });
  });

  it('passes interactive exclusions to panning to avoid drag conflicts', () => {
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    const excluded = (latestTransformWrapperProps?.panning as { excluded?: string[] }).excluded ?? [];
    expect(excluded).toContain('mask-overlay-handle');
    expect(excluded).toContain('mask-overlay-control');
  });

  it('keeps trackpad pinch zoom enabled while using wheel panning in select mode', () => {
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    const wheel = (latestTransformWrapperProps?.wheel as { wheelDisabled?: boolean; touchPadDisabled?: boolean }) ?? {};
    const panning = (latestTransformWrapperProps?.panning as { wheelPanning?: boolean }) ?? {};

    expect(wheel.wheelDisabled).toBe(true);
    expect(wheel.touchPadDisabled).toBe(false);
    expect(panning.wheelPanning).toBe(true);
  });

  it('does not enable library auto-centering flags in the viewport', () => {
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    expect(latestTransformWrapperProps?.centerZoomedOut).toBeUndefined();
    expect(latestTransformWrapperProps?.centerOnInit).toBeUndefined();
  });

  it('allows panning outside the container bounds', () => {
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    expect(latestTransformWrapperProps?.limitToBounds).toBe(false);
  });

  it('leaves the transform content element unconstrained so library bounds can use the full page size', () => {
    const controller = createMaskController();
    render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

    expect(latestTransformComponentProps?.contentClass).toBeUndefined();
  });

  it('keeps the current transform when the image url changes', async () => {
    const OriginalImage = globalThis.Image;

    class InstantImage {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      decoding = 'async';

      set src(_: string) {
        setTimeout(() => {
          this.onload?.();
        }, 0);
      }

      decode() {
        return Promise.resolve();
      }
    }

    vi.stubGlobal('Image', InstantImage as unknown as typeof Image);

    try {
      const controller = createMaskController();
      const { rerender } = render(<Workspace imageUrl="/page-a.png" maskController={controller} />);

      rerender(<Workspace imageUrl="/page-b.png" maskController={controller} />);

      await waitFor(() => {
        expect(screen.getByAltText('Manga Page')).toHaveAttribute('src', '/page-b.png');
      });
    } finally {
      vi.stubGlobal('Image', OriginalImage);
    }
  });
});
