from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.services.psd_export.models import PsdWriteSpec


class BasePsdWriter(ABC):
    writer_name: str = "base"
    writer_version: str = "0"

    @abstractmethod
    def write(self, spec: PsdWriteSpec, out_psd_path: Path, out_manifest_path: Path) -> dict:
        """Write PSD + manifest and return manifest dictionary."""
        raise NotImplementedError
