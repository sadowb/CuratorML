from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services.reading_order import (
    build_reading_order,
    _partition_panels_for_double_page_spread,
)


def _region(kind: str, bbox: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        region_kind=kind,
        bbox_json=bbox,
        polygon_json=None,
        confidence=0.95,
    )


def test_build_reading_order_handles_double_page_spread() -> None:
    # Layout:
    # right page panels: RT, RB
    # left page panels: LT, LB
    rt = _region("panel", [1100.0, 20.0, 1900.0, 420.0])
    rb = _region("panel", [1100.0, 470.0, 1900.0, 930.0])
    lt = _region("panel", [100.0, 20.0, 900.0, 420.0])
    lb = _region("panel", [100.0, 470.0, 900.0, 930.0])

    groups = build_reading_order([rt, rb, lt, lb], image_shape=(1000, 2000))
    ordered_panel_ids = [group.panel.id for group in groups]

    assert ordered_panel_ids == [rt.id, rb.id, lt.id, lb.id]


def test_partition_rejects_huge_center_crossing_panel() -> None:
    huge = _region("panel", [50.0, 40.0, 1950.0, 940.0])  # crosses seam and dominates width
    right = _region("panel", [1200.0, 80.0, 1800.0, 420.0])
    left = _region("panel", [200.0, 80.0, 800.0, 420.0])

    partition = _partition_panels_for_double_page_spread([huge, right, left], image_shape=(1000, 2000))

    assert partition is None

