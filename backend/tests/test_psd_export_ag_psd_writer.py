from __future__ import annotations

import uuid

import numpy as np
import pytest

from app.services.psd_export.models import CanvasSize, PsdLayerSpec, PsdWriteSpec, TranslatedTextBlock
from app.services.psd_export.writers.ag_psd_writer import AgPsdWriter


def _solid_rgba(width: int, height: int, rgba: tuple[int, int, int, int]) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[:, :] = rgba
    return image


def _transparent_rgba(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 4), dtype=np.uint8)


def test_ag_psd_writer_preserves_group_structure_and_text_fallback(tmp_path) -> None:
    psd_tools = pytest.importorskip("psd_tools")

    writer = AgPsdWriter()
    canvas = CanvasSize(width=120, height=90)
    region_id = uuid.uuid4()

    base = _solid_rgba(120, 90, (245, 240, 230, 255))
    mask = _transparent_rgba(120, 90)
    mask[20:70, 30:100] = (255, 0, 0, 120)
    text_pixels = _transparent_rgba(120, 90)
    text_pixels[36:48, 44:86] = (0, 0, 0, 255)

    text_block = TranslatedTextBlock(
        id=uuid.uuid4(),
        name="Dialogue 1",
        translated_text="Hello PSD",
        x=30,
        y=20,
        width=70,
        height=50,
        group="Dialogue",
        font_size=18,
        font_name="Arial",
        font_weight="bold",
        color="#111111",
        region_id=region_id,
    )

    spec = PsdWriteSpec.build(
        export_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        root_name="Grouped PSD Test",
        canvas=canvas,
        group_order=[
            "00_Base",
            "10_Structure",
            "10_Structure/TextMasks",
            "20_Text",
            "20_Text/Dialogue",
        ],
        layers=[
            PsdLayerSpec(
                z_index=0,
                layer_id="base_original",
                name="Original",
                group_path="00_Base",
                source_kind="page_file",
                source_ids={},
                asset_key="base_original",
            ),
            PsdLayerSpec(
                z_index=1,
                layer_id="mask_text",
                name="Text Mask",
                group_path="10_Structure/TextMasks",
                source_kind="region",
                source_ids={"region_id": str(region_id)},
                asset_key="mask_text",
                opacity=0.5,
            ),
            PsdLayerSpec(
                z_index=2,
                layer_id="dialogue_text_raster",
                name="Dialogue Text Raster",
                group_path="20_Text/Dialogue",
                source_kind="text",
                source_ids={"region_id": str(region_id)},
                asset_key="dialogue_text_raster",
            ),
        ],
        text_layers=[text_block],
        raster_assets={
            "base_original": base,
            "mask_text": mask,
            "dialogue_text_raster": text_pixels,
        },
        writer_name=writer.writer_name,
        writer_version=writer.writer_version,
        input_summary={},
        fallback_notes=[],
    )

    out_psd = tmp_path / "page.psd"
    out_manifest = tmp_path / "page_export_manifest.json"
    writer.write(spec, out_psd, out_manifest)

    psd = psd_tools.PSDImage.open(out_psd)
    top_level = {layer.name: layer for layer in psd}
    assert list(top_level) == ["Text", "Structure", "Base"]

    text_group = top_level["Text"]
    assert text_group.is_group()
    dialogue_group = {layer.name: layer for layer in text_group}["Dialogue"]
    assert dialogue_group.is_group()
    text_layer = dialogue_group[0]
    assert text_layer.kind == "type"
    assert text_layer.name == "Hello PSD"
    assert text_layer.bbox == (30, 20, 100, 70)

    structure_group = top_level["Structure"]
    text_masks_group = {layer.name: layer for layer in structure_group}["TextMasks"]
    assert text_masks_group.is_group()
    assert text_masks_group[0].name == "Text Mask"

    base_group = top_level["Base"]
    assert base_group.is_group()
    assert base_group[0].name == "Original"
