from __future__ import annotations

import uuid

import numpy as np

from app.services.psd_export.models import (
    CanvasSize,
    PageExportDocument,
    PageExportOptions,
    PageImageAsset,
    ResolvedPageAssets,
    ResolvedRasterAsset,
)
from app.services.psd_export.tree_builder import PsdExportTreeBuilder


def _asset(asset_key: str, name: str, kind: str, source_ids: dict[str, str]) -> ResolvedRasterAsset:
    return ResolvedRasterAsset(
        asset_key=asset_key,
        name=name,
        kind=kind,
        rgba=np.zeros((10, 12, 4), dtype=np.uint8),
        source_kind="page_region",
        source_ids=source_ids,
        fallback_used=False,
    )


def test_tree_builder_outputs_deterministic_structure() -> None:
    page_id = uuid.uuid4()
    region_id = uuid.uuid4()
    text_id = uuid.uuid4()
    document = PageExportDocument(
        export_id=uuid.uuid4(),
        page_id=page_id,
        chapter_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        canvas=CanvasSize(width=12, height=10),
        original_image=PageImageAsset(
            file_id=uuid.uuid4(),
            file_kind="original",
            file_path="x",
            mime_type="image/png",
        ),
        options=PageExportOptions(),
    )
    resolved = ResolvedPageAssets(
        canvas=CanvasSize(width=12, height=10),
        original=_asset("base_original", "Original", "base_original", {"page_file_id": str(uuid.uuid4())}),
        inpainted=_asset("base_inpainted", "Inpainted", "base_inpainted", {"page_file_id": str(uuid.uuid4())}),
        panels=[_asset("panel_0", "PanelX", "panel_mask", {"region_id": str(region_id)})],
        balloons=[_asset("balloon_0", "BalloonX", "balloon_mask", {"region_id": str(region_id)})],
        text_masks=[_asset("textmask_0", "TextMaskX", "textmask", {"region_id": str(region_id)})],
        dialogue_text_layers=[
            _asset(
                f"text_{text_id}",
                f"Text_{text_id}__Region_{region_id}__Dialogue",
                "translated_text",
                {"text_id": str(text_id), "region_id": str(region_id)},
            )
        ],
        floating_text_layers=[],
        helper_layers=[],
        preview=None,
        merged_preview=None,
        input_summary={},
        fallback_notes=[],
    )

    builder = PsdExportTreeBuilder()
    spec = builder.build(
        document=document,
        resolved=resolved,
        writer_name="test_writer",
        writer_version="1",
    )

    assert spec.group_order == [
        "00_Base",
        "10_Structure",
        "10_Structure/Panels",
        "10_Structure/Balloons",
        "20_Text",
        "20_Text/Dialogue",
        "20_Text/Floating",
        "30_Helpers",
        "30_Helpers/TextMasks",
        "99_Preview",
    ]
    assert [layer.name for layer in spec.layers[:2]] == ["Original", "Inpainted"]
    text_layers = [layer for layer in spec.layers if layer.group_path == "20_Text/Dialogue"]
    assert len(text_layers) == 1
    assert "Text_" in text_layers[0].name
    assert "__Region_" in text_layers[0].name
    assert "__Dialogue" in text_layers[0].name
