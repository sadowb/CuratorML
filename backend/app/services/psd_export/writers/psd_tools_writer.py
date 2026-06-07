from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings
from app.services.psd_export.manifest import build_manifest
from app.services.psd_export.models import PsdWriteSpec
from app.services.psd_export.writers.base import BasePsdWriter


class PsdToolsWriter(BasePsdWriter):
    """PSD writer adapter backed by ``psd-tools``."""

    writer_name = "psd_tools"
    writer_version = "1"

    def write(self, spec: PsdWriteSpec, out_psd_path: Path, out_manifest_path: Path) -> dict:
        psd_tools = self._import_psd_tools()
        PSDImage = psd_tools["PSDImage"]
        Group = psd_tools["Group"]
        PixelLayer = psd_tools["PixelLayer"]

        out_psd_path.parent.mkdir(parents=True, exist_ok=True)
        out_manifest_path.parent.mkdir(parents=True, exist_ok=True)

        psd = PSDImage.new(mode="RGBA", size=(spec.canvas.width, spec.canvas.height), color=(0, 0, 0, 0))
        root_group = self._create_group(psd, name=spec.root_name)

        groups: dict[str, Any] = {}
        for group_path in spec.group_order:
            parent = root_group
            walk: list[str] = []
            for part in group_path.split("/"):
                walk.append(part)
                current_path = "/".join(walk)
                existing = groups.get(current_path)
                if existing is not None:
                    parent = existing
                    continue
                group = self._new_group(Group, parent=parent, name=part)
                self._append_layer(parent, group)
                groups[current_path] = group
                parent = group

        for layer in sorted(spec.layers, key=lambda item: item.z_index):
            rgba = spec.raster_assets.get(layer.asset_key)
            if rgba is None:
                raise ValueError(f"Raster asset missing for layer '{layer.asset_key}'")
            image = Image.fromarray(rgba, mode="RGBA")
            target_group = groups.get(layer.group_path, root_group)
            pixel_layer = self._new_pixel_layer(PixelLayer, image, parent=target_group, name=layer.name)
            self._set_layer_visibility(pixel_layer, layer.visible)
            self._set_layer_opacity(pixel_layer, layer.opacity)
            self._append_layer(target_group, pixel_layer)

        psd.save(str(out_psd_path))

        manifest = build_manifest(
            spec,
            output_psd_path=self._to_manifest_path(out_psd_path),
            output_manifest_path=self._to_manifest_path(out_manifest_path),
        )
        out_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def _import_psd_tools(self) -> dict[str, Any]:
        try:
            from psd_tools import PSDImage
            from psd_tools.api.layers import Group, PixelLayer
        except ImportError as exc:  # pragma: no cover - exercised by integration environment
            raise RuntimeError(
                "psd-tools is required for PSD export. Install backend dependency 'psd-tools'."
            ) from exc
        return {"PSDImage": PSDImage, "Group": Group, "PixelLayer": PixelLayer}

    def _create_group(self, container: Any, name: str) -> Any:
        if hasattr(container, "create_group"):
            try:
                return container.create_group(name=name)
            except TypeError:
                return container.create_group(name)
        return self._new_group(type(container), parent=container, name=name)

    def _new_group(self, group_cls: Any, *, parent: Any, name: str) -> Any:
        if hasattr(group_cls, "new"):
            try:
                return group_cls.new(parent=parent, name=name, open_folder=True)
            except TypeError:
                try:
                    return group_cls.new(parent=parent, name=name)
                except TypeError:
                    return group_cls.new(parent, name)
        try:
            return group_cls(parent=parent, name=name)
        except TypeError:
            return group_cls(parent, name)

    def _new_pixel_layer(self, pixel_layer_cls: Any, image: Image.Image, *, parent: Any, name: str) -> Any:
        if hasattr(pixel_layer_cls, "frompil"):
            try:
                return pixel_layer_cls.frompil(image, parent=parent, name=name, top=0, left=0)
            except TypeError:
                try:
                    return pixel_layer_cls.frompil(image, parent, name, 0, 0)
                except TypeError:
                    return pixel_layer_cls.frompil(image, parent, name)
        try:
            return pixel_layer_cls(parent=parent, image=image, name=name)
        except TypeError:
            return pixel_layer_cls(parent, image, name)

    def _append_layer(self, container: Any, layer: Any) -> None:
        if hasattr(container, "append"):
            container.append(layer)
            return
        if hasattr(container, "layers"):
            container.layers.append(layer)
            return
        raise ValueError("Unsupported psd-tools container type for appending layer")

    def _set_layer_visibility(self, layer: Any, visible: bool) -> None:
        for attr in ("visible", "is_visible"):
            if hasattr(layer, attr):
                try:
                    setattr(layer, attr, bool(visible))
                    return
                except Exception:
                    continue

    def _set_layer_opacity(self, layer: Any, opacity: float) -> None:
        normalized = max(0.0, min(1.0, float(opacity)))
        value_8bit = int(round(normalized * 255))
        for candidate in (value_8bit, normalized):
            if hasattr(layer, "opacity"):
                try:
                    setattr(layer, "opacity", candidate)
                    return
                except Exception:
                    continue

    def _to_manifest_path(self, absolute_path: Path) -> str:
        try:
            return str(absolute_path.resolve().relative_to(settings.storage_root_path.resolve()))
        except ValueError:
            return str(absolute_path)
