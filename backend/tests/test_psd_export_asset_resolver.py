from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.services.psd_export.asset_resolver import PsdExportAssetResolver
from app.services.psd_export.models import CanvasSize, PageExportDocument, PageExportOptions, PageImageAsset, RegionGeometry


def _write_image(path: Path, width: int, height: int, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((height, width, 3), value, dtype=np.uint8)
    cv2.imwrite(str(path), image)


def test_asset_resolver_rasterizes_masks_and_falls_back_to_original(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "storage_root", tmp_path)

    original_rel = "project_a/chapter_b/page_c/original.png"
    original_abs = tmp_path / original_rel
    _write_image(original_abs, width=120, height=90, value=240)

    document = PageExportDocument(
        export_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        canvas=CanvasSize(width=1, height=1),
        original_image=PageImageAsset(
            file_id=uuid.uuid4(),
            file_kind="original",
            file_path=original_rel,
            mime_type="image/png",
        ),
        inpainted_image=None,
        panel_masks=[
            RegionGeometry(
                id=uuid.uuid4(),
                name="PanelOne",
                region_kind="panel",
                polygon=None,
                bbox=[10, 12, 40, 45],
                source_region_id=uuid.uuid4(),
            )
        ],
        balloon_masks=[
            RegionGeometry(
                id=uuid.uuid4(),
                name="BalloonOne",
                region_kind="balloon",
                polygon=[[60, 20], [90, 20], [90, 55], [60, 55]],
                bbox=None,
                source_region_id=uuid.uuid4(),
            )
        ],
        options=PageExportOptions(),
    )

    resolver = PsdExportAssetResolver()
    resolved = resolver.resolve(document)

    assert resolved.canvas.width == 120
    assert resolved.canvas.height == 90
    assert resolved.inpainted.fallback_used is True
    assert resolved.panels[0].rgba.shape == (90, 120, 4)
    assert resolved.balloons[0].rgba.shape == (90, 120, 4)
    assert int(resolved.panels[0].rgba[..., 3].sum()) > 0
    assert int(resolved.balloons[0].rgba[..., 3].sum()) > 0
