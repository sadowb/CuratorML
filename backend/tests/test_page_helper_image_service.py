from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app.services.page_helper_image_service import PageHelperImageService


class FakeDbSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        return None


class FakeInpaintService:
    def __init__(self, repo) -> None:
        self.repo = repo
        self.called = False

    async def run_for_page(self, _db, *, page, pipeline_run_id):
        self.called = True
        self.repo.inpainted_after_trigger = SimpleNamespace(
            file_kind="inpainted",
            file_path=self.repo.inpainted_path,
            mime_type="image/png",
        )
        return {"auto": True, "pipeline_run_id": str(pipeline_run_id)}


class FakePageRepo:
    def __init__(self, *, inpainted_file, inpainted_path: str, regions, texts) -> None:
        self.inpainted_file = inpainted_file
        self.inpainted_after_trigger = None
        self.inpainted_path = inpainted_path
        self.regions = regions
        self.texts = texts
        self.mark_calls: list[str] = []
        self.created_files: list[object] = []

    async def get_current_file_by_kind(self, _db, _page_id, file_kind: str):
        if file_kind != "inpainted":
            return None
        return self.inpainted_after_trigger or self.inpainted_file

    async def get_active_regions(self, _db, _page_id, *, kinds=None):
        assert kinds == ["panel", "balloon", "text"]
        return self.regions

    async def get_texts_for_region_ids(self, _db, region_ids):
        return [text for text in self.texts if text.region_id in region_ids]

    async def mark_files_not_current(self, _db, *, page_id, file_kind: str):
        _ = page_id
        self.mark_calls.append(file_kind)

    async def create_file(self, _db, page_file):
        self.created_files.append(page_file)
        return page_file


def _write_image(path: Path, value: int = 255) -> None:
    image = np.full((140, 220, 3), value, dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), image)


@pytest.mark.asyncio
async def test_generate_grounded_helper_uses_inpainted_source_and_ocr_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    inpainted_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/run_x/page.png"
    _write_image(tmp_path / inpainted_rel)

    region_1 = SimpleNamespace(id=uuid.uuid4(), reading_order=1, bbox_json=[20, 20, 80, 70], polygon_json=None)
    region_2 = SimpleNamespace(id=uuid.uuid4(), reading_order=2, bbox_json=[90, 40, 150, 95], polygon_json=None)

    text_1 = SimpleNamespace(region_id=region_1.id, ocr_text_corrected="hello", ocr_text_raw=None)
    # empty text should be skipped
    text_2 = SimpleNamespace(region_id=region_2.id, ocr_text_corrected="", ocr_text_raw="")

    repo = FakePageRepo(
        inpainted_file=SimpleNamespace(file_kind="inpainted", file_path=inpainted_rel, mime_type="image/png"),
        inpainted_path=inpainted_rel,
        regions=[region_1, region_2],
        texts=[text_1, text_2],
    )

    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        chapter=SimpleNamespace(project_id=project_id),
    )

    result = await PageHelperImageService(page_repo=repo, inpaint_service=FakeInpaintService(repo)).generate_grounded_helper(
        db=FakeDbSession(),
        page=page,
        persist_debug=False,
    )

    assert result.source_file_kind == "inpainted"
    assert result.mime_type == "image/png"
    assert result.marker_count == 1
    assert result.skipped_regions == 1
    assert result.persisted_artifact_path is None
    assert repo.mark_calls == []
    assert repo.created_files == []
    assert len(result.image_bytes) > 0


@pytest.mark.asyncio
async def test_generate_grounded_helper_auto_triggers_inpaint_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    inpainted_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/run_auto/page.png"
    _write_image(tmp_path / inpainted_rel)

    region = SimpleNamespace(id=uuid.uuid4(), reading_order=1, bbox_json=[20, 20, 80, 70], polygon_json=None)
    text = SimpleNamespace(region_id=region.id, ocr_text_corrected=None, ocr_text_raw="raw")

    repo = FakePageRepo(
        inpainted_file=None,
        inpainted_path=inpainted_rel,
        regions=[region],
        texts=[text],
    )
    inpaint = FakeInpaintService(repo)
    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        chapter=SimpleNamespace(project_id=project_id),
    )

    db = FakeDbSession()
    result = await PageHelperImageService(page_repo=repo, inpaint_service=inpaint).generate_grounded_helper(
        db=db,
        page=page,
        persist_debug=False,
    )

    assert inpaint.called is True
    assert result.source_file_kind == "inpainted"
    assert result.marker_count == 1


@pytest.mark.asyncio
async def test_generate_grounded_helper_persists_debug_artifact_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    run_id = uuid.uuid4()
    inpainted_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/run_x/page.png"
    _write_image(tmp_path / inpainted_rel)

    region = SimpleNamespace(id=uuid.uuid4(), reading_order=1, bbox_json=[20, 20, 80, 70], polygon_json=None)
    text = SimpleNamespace(region_id=region.id, ocr_text_corrected="text", ocr_text_raw=None)

    repo = FakePageRepo(
        inpainted_file=SimpleNamespace(file_kind="inpainted", file_path=inpainted_rel, mime_type="image/png"),
        inpainted_path=inpainted_rel,
        regions=[region],
        texts=[text],
    )
    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        chapter=SimpleNamespace(project_id=project_id),
    )

    result = await PageHelperImageService(page_repo=repo, inpaint_service=FakeInpaintService(repo)).generate_grounded_helper(
        db=FakeDbSession(),
        page=page,
        pipeline_run_id=run_id,
        persist_debug=True,
    )

    assert result.persisted_artifact_path is not None
    assert "helper_grounded" in result.persisted_artifact_path
    assert repo.mark_calls == ["helper_grounded"]
    assert len(repo.created_files) == 1
    saved_path = tmp_path / result.persisted_artifact_path
    assert saved_path.exists()
