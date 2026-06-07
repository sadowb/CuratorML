from __future__ import annotations

import json
import uuid

import numpy as np
import pytest

from app.services.psd_export.models import CanvasSize, PsdLayerSpec, PsdWriteSpec
from app.services.psd_export.writers.psd_tools_writer import PsdToolsWriter


def test_psd_tools_writer_writes_psd_and_manifest(tmp_path) -> None:
    pytest.importorskip("psd_tools")

    writer = PsdToolsWriter()
    rgba = np.zeros((20, 30, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 3] = 255
    layer = PsdLayerSpec(
        z_index=0,
        layer_id="base_original",
        name="Original",
        group_path="00_Base",
        visible=True,
        source_kind="page_file",
        source_ids={"page_file_id": str(uuid.uuid4())},
        asset_key="base_original",
    )
    spec = PsdWriteSpec.build(
        export_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        root_name=f"Page_{uuid.uuid4()}",
        canvas=CanvasSize(width=30, height=20),
        group_order=["00_Base"],
        layers=[layer],
        raster_assets={"base_original": rgba},
        writer_name=writer.writer_name,
        writer_version=writer.writer_version,
        input_summary={"panel_masks": 0},
        fallback_notes=[],
    )
    out_psd = tmp_path / "page.psd"
    out_manifest = tmp_path / "page_export_manifest.json"
    manifest = writer.write(spec, out_psd, out_manifest)

    assert out_psd.exists()
    assert out_psd.stat().st_size > 0
    assert out_manifest.exists()
    loaded = json.loads(out_manifest.read_text(encoding="utf-8"))
    assert loaded["writer"] == writer.writer_name
    assert loaded["layers"][0]["name"] == "Original"
    assert manifest["layers"][0]["name"] == "Original"
