from __future__ import annotations

from typing import Any

from app.services.psd_export.models import PsdWriteSpec


def build_manifest(
    spec: PsdWriteSpec,
    *,
    output_psd_path: str,
    output_manifest_path: str,
) -> dict[str, Any]:
    ordered_layers = sorted(spec.layers, key=lambda layer: layer.z_index)
    layer_rows: list[dict[str, Any]] = []
    for layer in ordered_layers:
        layer_rows.append(
            {
                "z_index": layer.z_index,
                "layer_id": layer.layer_id,
                "name": layer.name,
                "group_path": layer.group_path,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "blend_mode": layer.blend_mode,
                "source_kind": layer.source_kind,
                "source_ids": layer.source_ids,
                "fallback_used": layer.fallback_used,
            }
        )

    return {
        "export_id": str(spec.export_id),
        "page_id": str(spec.page_id),
        "writer": spec.writer_name,
        "writer_version": spec.writer_version,
        "created_at": spec.created_at.isoformat(),
        "canvas": {
            "width": spec.canvas.width,
            "height": spec.canvas.height,
        },
        "outputs": {
            "psd": output_psd_path,
            "manifest": output_manifest_path,
        },
        "input_summary": spec.input_summary,
        "fallback_notes": spec.fallback_notes,
        "layer_order": [layer["layer_id"] for layer in layer_rows],
        "layers": layer_rows,
    }
