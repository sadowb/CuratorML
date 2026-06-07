from __future__ import annotations

import io
import uuid
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
import numpy as np

from app.utils.storage import build_page_artifact_storage_path, build_page_storage_path, save_cv2_image, save_upload_file


def test_build_page_storage_path_uses_page_id_segment() -> None:
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()

    path = build_page_storage_path(
        project_id=str(project_id),
        chapter_id=str(chapter_id),
        page_id=str(page_id),
        filename_suffix=".jpg",
        file_kind="original",
    )

    assert str(path) == f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/original.jpg"


@pytest.mark.asyncio
async def test_save_upload_file_refuses_to_overwrite_existing_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    relative_path = build_page_storage_path(
        project_id="p",
        chapter_id="c",
        page_id="x",
        filename_suffix=".jpg",
        file_kind="original",
    )
    absolute_path = tmp_path / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(b"existing")

    upload = UploadFile(filename="new.jpg", file=io.BytesIO(b"new-content"))
    with pytest.raises(ValueError, match="refusing to overwrite"):
        await save_upload_file(upload, relative_path)


def test_build_page_artifact_storage_path_uses_artifacts_directory() -> None:
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    run_id = uuid.uuid4()

    path = build_page_artifact_storage_path(
        project_id=str(project_id),
        chapter_id=str(chapter_id),
        page_id=str(page_id),
        artifact_kind="inpainted",
        artifact_name="erasure_mask.png",
        run_id=str(run_id),
    )

    assert str(path) == (
        f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/"
        f"artifacts/inpainted/run_{run_id}/erasure_mask.png"
    )


@pytest.mark.asyncio
async def test_save_cv2_image_writes_under_storage_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    relative_path = build_page_artifact_storage_path(
        project_id="p",
        chapter_id="c",
        page_id="x",
        artifact_kind="inpainted",
        artifact_name="page.png",
        run_id="run-1",
    )
    image = np.zeros((8, 8), dtype=np.uint8)

    destination = await save_cv2_image(image, relative_path)

    assert destination == tmp_path / relative_path
    assert destination.exists()
