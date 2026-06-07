import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import MaskOverlay from '../MaskOverlay';
import { useMaskOverlayInteractions } from '../../../hooks/editor/useMaskOverlayInteractions';

function OverlayHarness({
  onRegionPolygonChange,
  onRegionSelect,
  onRegionDelete,
  mode = 'select',
}: {
  onRegionPolygonChange: (regionId: string, polygon: number[][]) => void;
  onRegionSelect: (regionId: string) => void;
  onRegionDelete: (regionId: string) => void;
  mode?: 'select' | 'erase' | 'none';
}) {
  const regions = [
    {
      id: 'region-1',
      regionKind: 'text',
      displayPolygon: [
        [10, 10],
        [50, 10],
        [50, 50],
      ],
      editablePolygon: [
        [10, 10],
        [50, 10],
        [50, 50],
      ],
    },
  ];

  const interactions = useMaskOverlayInteractions({
    mode,
    naturalSize: { width: 100, height: 100 },
    regions: regions.map((region) => ({
      id: region.id,
      regionKind: region.regionKind,
      editablePolygon: region.editablePolygon,
    })),
    onRegionPolygonChange,
    onRegionSelect,
    onRegionDelete,
  });

  return (
    <MaskOverlay
      regions={regions}
      naturalSize={{ width: 100, height: 100 }}
      visible
      showLabels={false}
      interactive={mode !== 'none'}
      showHandles={mode === 'select'}
      eraseMode={mode === 'erase'}
      activeMaskId={null}
      isDragging={interactions.isDragging}
      onOverlayPointerMove={interactions.onOverlayPointerMove}
      onOverlayPointerUp={interactions.onOverlayPointerUp}
      onOverlayPointerCancel={interactions.onOverlayPointerCancel}
      onHandlePointerDown={interactions.onHandlePointerDown}
      onPolygonPointerDown={interactions.onPolygonPointerDown}
    />
  );
}

describe('Mask overlay interactions', () => {
  it('updates polygon points while dragging a vertex handle', () => {
    const onRegionPolygonChange = vi.fn();
    const onRegionSelect = vi.fn();
    const onRegionDelete = vi.fn();

    const { container } = render(
      <OverlayHarness
        onRegionPolygonChange={onRegionPolygonChange}
        onRegionSelect={onRegionSelect}
        onRegionDelete={onRegionDelete}
      />,
    );

    const overlay = screen.getByLabelText('Mask overlay') as unknown as SVGSVGElement;
    vi.spyOn(overlay, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
      toJSON: () => ({}),
    } as DOMRect);

    const handle = container.querySelector('.mask-overlay-handle') as SVGCircleElement;
    expect(handle).toBeTruthy();

    fireEvent.pointerDown(handle, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(overlay, { clientX: 30, clientY: 40, pointerId: 1 });
    fireEvent.pointerUp(overlay, { pointerId: 1 });

    expect(onRegionSelect).toHaveBeenCalledWith('region-1');
    expect(onRegionPolygonChange).toHaveBeenCalledTimes(1);
    expect(onRegionPolygonChange).toHaveBeenCalledWith(
      'region-1',
      [
        [30, 40],
        [50, 10],
        [50, 50],
      ],
    );
  });

  it('moves the whole polygon while dragging inside the mask', () => {
    const onRegionPolygonChange = vi.fn();
    const onRegionSelect = vi.fn();
    const onRegionDelete = vi.fn();

    const { container } = render(
      <OverlayHarness
        onRegionPolygonChange={onRegionPolygonChange}
        onRegionSelect={onRegionSelect}
        onRegionDelete={onRegionDelete}
      />,
    );

    const overlay = screen.getByLabelText('Mask overlay') as unknown as SVGSVGElement;
    vi.spyOn(overlay, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
      toJSON: () => ({}),
    } as DOMRect);

    const polygon = container.querySelector('.mask-overlay-polygon') as SVGPolygonElement;
    expect(polygon).toBeTruthy();

    fireEvent.pointerDown(polygon, { clientX: 20, clientY: 20, pointerId: 1 });
    fireEvent.pointerMove(overlay, { clientX: 40, clientY: 35, pointerId: 1 });
    fireEvent.pointerUp(overlay, { pointerId: 1 });

    expect(onRegionSelect).toHaveBeenCalledWith('region-1');
    expect(onRegionPolygonChange).toHaveBeenCalledWith(
      'region-1',
      [
        [30, 25],
        [70, 25],
        [70, 65],
      ],
    );
  });

  it('deletes a mask when eraser mode is active', () => {
    const onRegionPolygonChange = vi.fn();
    const onRegionSelect = vi.fn();
    const onRegionDelete = vi.fn();

    const { container } = render(
      <OverlayHarness
        mode="erase"
        onRegionPolygonChange={onRegionPolygonChange}
        onRegionSelect={onRegionSelect}
        onRegionDelete={onRegionDelete}
      />,
    );

    const polygon = container.querySelector('.mask-overlay-polygon') as SVGPolygonElement;
    expect(polygon).toBeTruthy();

    fireEvent.pointerDown(polygon, { clientX: 20, clientY: 20, pointerId: 1 });

    expect(onRegionSelect).toHaveBeenCalledWith('region-1');
    expect(onRegionDelete).toHaveBeenCalledWith('region-1');
    expect(onRegionPolygonChange).not.toHaveBeenCalled();
  });
});
