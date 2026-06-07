from __future__ import annotations

import numpy as np

from app.services.psd_export.models import (
    PageExportDocument,
    PsdLayerSpec,
    PsdWriteSpec,
    ResolvedPageAssets,
    ResolvedRasterAsset,
)


class PsdExportTreeBuilder:
    """Stage 3: build deterministic PSD layer/group tree spec."""

    GROUP_ORDER = [
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

    def build(
        self,
        *,
        document: PageExportDocument,
        resolved: ResolvedPageAssets,
        writer_name: str,
        writer_version: str,
    ) -> PsdWriteSpec:
        layers: list[PsdLayerSpec] = []
        raster_assets: dict[str, np.ndarray] = {}
        z = 0

        def add_layer(
            asset: ResolvedRasterAsset,
            *,
            group_path: str,
            visible: bool,
            opacity: float = 1.0,
        ) -> None:
            nonlocal z
            layer = PsdLayerSpec(
                z_index=z,
                layer_id=asset.asset_key,
                name=asset.name,
                group_path=group_path,
                visible=visible,
                opacity=opacity,
                blend_mode="normal",
                source_kind=asset.source_kind,
                source_ids={k: v for k, v in asset.source_ids.items() if v},
                fallback_used=asset.fallback_used,
                asset_key=asset.asset_key,
            )
            layers.append(layer)
            raster_assets[asset.asset_key] = asset.rgba
            z += 1

        add_layer(
            resolved.original,
            group_path="00_Base",
            visible=document.options.original_visible,
        )
        add_layer(
            resolved.inpainted,
            group_path="00_Base",
            visible=document.options.inpainted_visible,
        )

        for asset in resolved.panels:
            panel_id = asset.source_ids.get("region_id", "unknown")
            asset.name = f"Panel_{panel_id}"
            add_layer(asset, group_path="10_Structure/Panels", visible=False)

        for asset in resolved.balloons:
            balloon_id = asset.source_ids.get("region_id", "unknown")
            asset.name = f"Balloon_{balloon_id}"
            add_layer(asset, group_path="10_Structure/Balloons", visible=False)

        for asset in resolved.dialogue_text_layers:
            add_layer(asset, group_path="20_Text/Dialogue", visible=True)

        for asset in resolved.floating_text_layers:
            add_layer(asset, group_path="20_Text/Floating", visible=True)

        for asset in resolved.text_masks:
            region_id = asset.source_ids.get("region_id", "unknown")
            asset.name = f"TextMask_{region_id}"
            add_layer(asset, group_path="30_Helpers/TextMasks", visible=document.options.helper_layers_visible)

        for asset in resolved.helper_layers:
            add_layer(asset, group_path="30_Helpers", visible=document.options.helper_layers_visible)

        preview_asset = resolved.merged_preview or resolved.preview
        if preview_asset is not None:
            preview_asset.name = "Preview"
            add_layer(preview_asset, group_path="99_Preview", visible=True)

        return PsdWriteSpec.build(
            export_id=document.export_id,
            page_id=document.page_id,
            root_name=f"Page_{document.page_id}",
            canvas=resolved.canvas,
            group_order=list(self.GROUP_ORDER),
            layers=layers,
            text_layers=document.translated_text_blocks,
            raster_assets=raster_assets,
            writer_name=writer_name,
            writer_version=writer_version,
            input_summary=resolved.input_summary,
            fallback_notes=resolved.fallback_notes,
        )
