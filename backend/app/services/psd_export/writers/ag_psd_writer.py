from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.services.psd_export.manifest import build_manifest
from app.services.psd_export.models import PsdWriteSpec
from app.services.psd_export.writers.base import BasePsdWriter

logger = logging.getLogger(__name__)


class AgPsdWriter(BasePsdWriter):
    """PSD writer backed by Node.js ag-psd.

    Produces a PSD with:
    - Raster layers for base image, inpainted image, masks, preview.
    - Editable text layers (TySh) for Photoshop + rasterized pixel data for
      GIMP fallback rendering.
    """

    writer_name = "ag_psd"
    writer_version = "2"

    def write(self, spec: PsdWriteSpec, out_psd_path: Path, out_manifest_path: Path) -> dict:
        out_psd_path.parent.mkdir(parents=True, exist_ok=True)
        out_manifest_path.parent.mkdir(parents=True, exist_ok=True)

        temp_files: list[str] = []
        try:
            # ------------------------------------------------------------------
            # Write every raster asset to a temporary raw RGBA binary file so
            # Node.js can read it without needing a Python↔JS image codec.
            # ------------------------------------------------------------------
            raster_file_by_key: dict[str, str] = {}
            for key, rgba in spec.raster_assets.items():
                with tempfile.NamedTemporaryFile(suffix=".rgba", delete=False) as f:
                    f.write(np.asarray(rgba, dtype=np.uint8).tobytes())
                    raster_file_by_key[key] = f.name
                    temp_files.append(f.name)

            # ------------------------------------------------------------------
            # Build raster layer list (ordered bottom→top by z_index).
            # Skip text-group layers — those are handled as text layers below.
            # ------------------------------------------------------------------
            raster_layers = []
            text_raster_by_region_id: dict[str, str] = {}

            for layer in sorted(spec.layers, key=lambda l: l.z_index):
                if layer.asset_key not in raster_file_by_key:
                    continue

                if "20_Text" in layer.group_path:
                    # Map region_id → temp RGBA file for text pixel-data fallback.
                    rid = layer.source_ids.get("region_id")
                    if rid:
                        text_raster_by_region_id[rid] = raster_file_by_key[layer.asset_key]
                    continue

                rgba = np.asarray(spec.raster_assets[layer.asset_key], dtype=np.uint8)
                raster_layers.append(
                    {
                        "name": layer.name,
                        "groupPath": layer.group_path,
                        "zIndex": layer.z_index,
                        "visible": layer.visible,
                        "opacity": layer.opacity,
                        "imagePath": raster_file_by_key[layer.asset_key],
                        "imageW": int(rgba.shape[1]),
                        "imageH": int(rgba.shape[0]),
                        "x": 0,
                        "y": 0,
                    }
                )

            # ------------------------------------------------------------------
            # Build text layer list.
            # For each text block, crop the matching raster asset to the text
            # bounding box so ag-psd can embed it as the GIMP-visible pixel data.
            # ------------------------------------------------------------------
            text_layers = []
            cw, ch = spec.canvas.width, spec.canvas.height

            for t in spec.text_layers:
                entry: dict = {
                    "text": t.translated_text,
                    "x": t.x,
                    "y": t.y,
                    "w": t.width,
                    "h": t.height,
                    "color": t.color,
                    "fontSize": t.font_size,
                    "font": t.font_name,
                    "fontWeight": t.font_weight,
                    "groupPath": f"20_Text/{t.group}",
                    "zIndex": 100000 + len(text_layers),
                    "textAlign": "center",
                }

                rid = str(t.region_id) if t.region_id else None
                if rid and rid in text_raster_by_region_id:
                    full_rgba_path = text_raster_by_region_id[rid]
                    full_rgba = spec.raster_assets.get(
                        next(
                            (
                                l.asset_key
                                for l in spec.layers
                                if l.source_ids.get("region_id") == rid
                            ),
                            "",
                        )
                    )
                    if full_rgba is not None:
                        # Crop to text bounding box — imageData must match layer bounds.
                        x1 = max(0, int(round(t.x)))
                        y1 = max(0, int(round(t.y)))
                        x2 = min(cw, int(round(t.x + t.width)))
                        y2 = min(ch, int(round(t.y + t.height)))
                        if x2 > x1 and y2 > y1:
                            cropped = np.asarray(full_rgba, dtype=np.uint8)[y1:y2, x1:x2]
                            with tempfile.NamedTemporaryFile(suffix=".rgba", delete=False) as f:
                                f.write(cropped.tobytes())
                                entry["imagePath"] = f.name
                                entry["imageW"] = x2 - x1
                                entry["imageH"] = y2 - y1
                                # Adjust layer position to cropped area.
                                entry["x"] = x1
                                entry["y"] = y1
                                entry["w"] = x2 - x1
                                entry["h"] = y2 - y1
                                temp_files.append(f.name)

                text_layers.append(entry)

            # ------------------------------------------------------------------
            # Write Node.js manifest and invoke the export script.
            # ------------------------------------------------------------------
            node_manifest = {
                "width": cw,
                "height": ch,
                "rasterLayers": raster_layers,
                "textLayers": text_layers,
                "groupOrder": spec.group_order,
            }

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
                json.dump(node_manifest, tf)
                manifest_temp_path = tf.name
                temp_files.append(manifest_temp_path)

            script_path = Path(__file__).with_name("export_psd.js")

            process = subprocess.run(
                ["node", str(script_path), manifest_temp_path, str(out_psd_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                error_msg = process.stderr or process.stdout
                logger.error("Node.js PSD export failed: %s", error_msg)
                raise RuntimeError(f"PSD generation failed: {error_msg}")

        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except OSError:
                    pass

        manifest = build_manifest(
            spec,
            output_psd_path=self._to_manifest_path(out_psd_path),
            output_manifest_path=self._to_manifest_path(out_manifest_path),
        )
        out_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def _to_manifest_path(self, absolute_path: Path) -> str:
        try:
            return str(absolute_path.resolve().relative_to(settings.storage_root_path.resolve()))
        except ValueError:
            return str(absolute_path)
