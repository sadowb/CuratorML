from __future__ import annotations

from pathlib import Path
import asyncio
import shutil
import uuid

import aiofiles
from fastapi import UploadFile
import numpy as np
import cv2

from app.core.config import settings


def build_page_storage_path(
    project_id: str,
    chapter_id: str,
    page_id: str,
    filename_suffix: str,
    file_kind: str = "original",
) -> Path:
    return Path(
        f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/{file_kind}{filename_suffix}"
    )


def build_page_artifact_storage_path(
    project_id: str,
    chapter_id: str,
    page_id: str,
    artifact_kind: str,
    artifact_name: str,
    *,
    run_id: str | None = None,
) -> Path:
    base = Path(f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/{artifact_kind}")
    if run_id:
        base = base / f"run_{run_id}"
    return base / artifact_name


async def save_upload_file(upload_file: UploadFile, relative_path: Path) -> None:
    destination = settings.storage_root_path / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("Original file path already exists; refusing to overwrite")

    async with aiofiles.open(destination, "wb") as out_file:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            await out_file.write(chunk)

    await upload_file.seek(0)


def resolve_storage_path(relative_path: str) -> Path:
    root = settings.storage_root_path.resolve()
    candidate = (root / relative_path).resolve()
    candidate.relative_to(root)
    return candidate


async def save_cv2_image(image: np.ndarray, relative_path: Path) -> Path:
    destination = resolve_storage_path(str(relative_path))
    destination.parent.mkdir(parents=True, exist_ok=True)

    def _write() -> bool:
        return bool(cv2.imwrite(str(destination), image))

    if not await asyncio.to_thread(_write):
        raise ValueError(f"Failed to write image artifact to storage: {relative_path}")
    return destination


def remove_project_storage(project_id: uuid.UUID) -> None:
    project_dir = settings.storage_root_path / f"project_{project_id}"
    if project_dir.exists() and project_dir.is_dir():
        shutil.rmtree(project_dir)
