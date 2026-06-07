from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app.schemas.job import InpaintOptions
from app.services.inpaint_page_service import InpaintPageService


class FakePageRepo:
    def __init__(
        self,
        *,
        source_file,
        text_regions,
        balloon_regions=None,
        current_inpainted=None,
        current_mask=None,
    ) -> None:
        self.source_file = source_file
        self.text_regions = text_regions
        self.balloon_regions = balloon_regions or []
        self.current_inpainted = current_inpainted
        self.current_mask = current_mask
        self.mark_not_current_calls: list[tuple[str, str]] = []
        self.created_files: list[object] = []

    async def get_current_file_by_kind(self, _db, _page_id, file_kind: str):
        if file_kind == "original":
            return self.source_file
        if file_kind == "inpainted":
            return self.current_inpainted
        if file_kind == "inpaint_mask":
            return self.current_mask
        return None

    async def get_active_regions(self, _db, _page_id, *, kinds=None):
        if kinds == ["text"]:
            return self.text_regions
        if kinds == ["balloon"]:
            return self.balloon_regions
        return self.text_regions

    async def mark_files_not_current(self, _db, *, page_id, file_kind: str):
        self.mark_not_current_calls.append((str(page_id), file_kind))

    async def create_file(self, _db, page_file):
        self.created_files.append(page_file)
        return page_file


def test_build_mask_prefers_text_polygon_over_bbox_for_ai_text() -> None:
    service = InpaintPageService()
    text_region = SimpleNamespace(
        region_kind="text",
        bbox_json=[10.0, 10.0, 20.0, 20.0],
        polygon_json=[[60.0, 60.0], [80.0, 60.0], [80.0, 80.0], [60.0, 80.0]],
        origin="mask_inference",
    )

    mask = service._build_mask(
        (100, 100),
        [text_region],
        options=InpaintOptions(ai_expand_strength=0.0),
    )

    assert mask[15, 15] == 0
    assert mask[70, 70] > 0


def test_build_mask_does_not_expand_manual_text_polygon() -> None:
    service = InpaintPageService()
    text_region = SimpleNamespace(
        region_kind="text",
        bbox_json=[10.0, 10.0, 20.0, 20.0],
        polygon_json=[[60.0, 60.0], [62.0, 60.0], [62.0, 62.0], [60.0, 62.0]],
        origin="user_edited",
    )

    mask = service._build_mask(
        (100, 100),
        [text_region],
        options=InpaintOptions(ai_expand_strength=1.0),
    )

    # Keep exact user geometry: neighboring pixel outside polygon stays untouched.
    assert mask[59, 61] == 0
    assert mask[61, 61] > 0


def test_build_mask_applies_text_grow_to_manual_text_polygon() -> None:
    service = InpaintPageService()
    text_region = SimpleNamespace(
        region_kind="text",
        bbox_json=[10.0, 10.0, 20.0, 20.0],
        polygon_json=[[60.0, 60.0], [62.0, 60.0], [62.0, 62.0], [60.0, 62.0]],
        origin="user_edited",
    )

    mask = service._build_mask(
        (100, 100),
        [text_region],
        options=InpaintOptions(ai_expand_strength=0.0, text_expand_px=2.0),
    )

    # With explicit text grow, pixels around manual geometry should be covered.
    assert mask[59, 61] > 0
    assert mask[61, 61] > 0


def test_text_expand_px_supports_40_for_manual_regions() -> None:
    service = InpaintPageService()
    text_region = SimpleNamespace(
        region_kind="text",
        bbox_json=[10.0, 10.0, 20.0, 20.0],
        polygon_json=[[60.0, 60.0], [62.0, 60.0], [62.0, 62.0], [60.0, 62.0]],
        origin="user_edited",
    )

    expand_px = service._text_expand_px(
        text_region,
        InpaintOptions(ai_expand_strength=0.0, text_expand_px=40.0),
    )

    assert expand_px == 40


def test_smart_inpaint_assigns_text_to_balloon_by_overlap_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InpaintPageService()
    image = np.full((120, 120, 3), 255, dtype=np.uint8)

    balloon = SimpleNamespace(
        id="b1",
        region_kind="balloon",
        bbox_json=[20.0, 20.0, 80.0, 80.0],
        polygon_json=[[20.0, 20.0], [80.0, 20.0], [80.0, 80.0], [20.0, 80.0]],
        confidence=0.5,
    )
    text = SimpleNamespace(
        id="t1",
        region_kind="text",
        bbox_json=[70.0, 40.0, 110.0, 60.0],  # center is outside balloon
        polygon_json=[[60.0, 40.0], [79.0, 40.0], [79.0, 60.0], [60.0, 60.0]],
        parent_region_id=None,
        confidence=1.0,
        origin="mask_inference",
    )

    calls: list[np.ndarray] = []
    original_inpaint = cv2.inpaint

    def tracked_inpaint(src, inpaint_mask, *args, **kwargs):
        calls.append(inpaint_mask.copy())
        return original_inpaint(src, inpaint_mask, *args, **kwargs)

    monkeypatch.setattr(cv2, "inpaint", tracked_inpaint)

    service._smart_inpaint(
        image,
        [text],
        [balloon],
        options=InpaintOptions(ai_expand_strength=0.0),
    )

    # If overlap fallback works, text is processed in the balloon path and does
    # not fall through to orphan inpaint.
    assert calls == []


def test_smart_inpaint_falls_back_to_orphan_inpaint_when_balloon_coverage_is_too_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InpaintPageService()
    image = np.full((120, 120, 3), 255, dtype=np.uint8)

    # Intentionally bad balloon geometry: very narrow strip.
    balloon = SimpleNamespace(
        id="b1",
        region_kind="balloon",
        bbox_json=[45.0, 10.0, 55.0, 110.0],
        polygon_json=[[45.0, 10.0], [55.0, 10.0], [55.0, 110.0], [45.0, 110.0]],
        confidence=0.3,
    )
    text = SimpleNamespace(
        id="t1",
        region_kind="text",
        bbox_json=[30.0, 45.0, 85.0, 75.0],
        polygon_json=None,
        parent_region_id="b1",
        confidence=0.2,
        origin="mask_inference",
    )

    calls: list[np.ndarray] = []
    original_inpaint = cv2.inpaint

    def tracked_inpaint(src, inpaint_mask, *args, **kwargs):
        calls.append(inpaint_mask.copy())
        return original_inpaint(src, inpaint_mask, *args, **kwargs)

    monkeypatch.setattr(cv2, "inpaint", tracked_inpaint)

    # With fallback mode "no_clip", low coverage keeps the raw text mask.
    service._smart_inpaint(
        image,
        [text],
        [balloon],
        options=InpaintOptions(
            method="telea",
            ai_expand_strength=0.0,
            clip_fallback_mode="no_clip",
            balloon_safe_inset_mode="manual",
            balloon_safe_inset_px=6.0,
        ),
    )

    assert len(calls) == 1
    # The fallback must include text pixels outside the narrow balloon strip.
    assert calls[0][60, 35] > 0
    assert calls[0][60, 80] > 0


def test_smart_inpaint_falls_back_to_orphan_inpaint_when_balloon_is_too_text_dense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InpaintPageService()
    image = np.full((140, 140, 3), 255, dtype=np.uint8)

    # Balloon tightly wraps the text: high text density should bypass
    # balloon median-fill logic.
    balloon = SimpleNamespace(
        id="b1",
        region_kind="balloon",
        bbox_json=[40.0, 20.0, 95.0, 125.0],
        polygon_json=[[40.0, 20.0], [95.0, 20.0], [95.0, 125.0], [40.0, 125.0]],
        confidence=0.9,
    )
    text = SimpleNamespace(
        id="t1",
        region_kind="text",
        bbox_json=[48.0, 28.0, 88.0, 118.0],
        polygon_json=None,
        parent_region_id="b1",
        confidence=0.2,
        origin="mask_inference",
    )

    calls: list[np.ndarray] = []
    original_inpaint = cv2.inpaint

    def tracked_inpaint(src, inpaint_mask, *args, **kwargs):
        calls.append(inpaint_mask.copy())
        return original_inpaint(src, inpaint_mask, *args, **kwargs)

    monkeypatch.setattr(cv2, "inpaint", tracked_inpaint)

    service._smart_inpaint(
        image,
        [text],
        [balloon],
        options=InpaintOptions(ai_expand_strength=0.0),
    )

    assert len(calls) == 1
    assert calls[0][70, 70] > 0


@pytest.mark.asyncio
async def test_run_for_page_reuses_existing_inpaint_when_image_and_mask_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    pipeline_run_id = uuid.uuid4()

    source_relative = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/original.png"
    source_path = tmp_path / source_relative
    source_path.parent.mkdir(parents=True, exist_ok=True)

    source_image = np.full((32, 32, 3), 255, dtype=np.uint8)
    source_image[12:20, 12:20] = 0
    assert cv2.imwrite(str(source_path), source_image)

    text_region = SimpleNamespace(
        id="t1",
        region_kind="text",
        bbox_json=[12.0, 12.0, 20.0, 20.0],
        polygon_json=[[1.0, 1.0], [5.0, 1.0], [5.0, 5.0], [1.0, 5.0]],
        parent_region_id=None,
        confidence=0.2,
        origin="mask_inference",
    )

    service = InpaintPageService()
    generated_mask = service._build_mask(source_image.shape[:2], [text_region])
    generated_inpaint = cv2.inpaint(source_image, generated_mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

    existing_inpaint_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/existing/page.png"
    existing_mask_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/existing/erasure_mask.png"
    existing_inpaint_path = tmp_path / existing_inpaint_rel
    existing_mask_path = tmp_path / existing_mask_rel
    existing_inpaint_path.parent.mkdir(parents=True, exist_ok=True)
    existing_mask_path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(existing_inpaint_path), generated_inpaint)
    assert cv2.imwrite(str(existing_mask_path), generated_mask)

    source_file = SimpleNamespace(file_path=source_relative, mime_type="image/png")
    current_inpainted_file = SimpleNamespace(file_path=existing_inpaint_rel)
    current_mask_file = SimpleNamespace(file_path=existing_mask_rel)

    repo = FakePageRepo(
        source_file=source_file,
        text_regions=[text_region],
        balloon_regions=[],
        current_inpainted=current_inpainted_file,
        current_mask=current_mask_file,
    )

    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        chapter=SimpleNamespace(project_id=project_id),
    )

    save_calls: list[str] = []

    async def fake_save_cv2_image(_image, _relative_path):
        save_calls.append(str(_relative_path))
        return tmp_path / _relative_path

    monkeypatch.setattr("app.services.inpaint_page_service.save_cv2_image", fake_save_cv2_image)

    result = await InpaintPageService(page_repo=repo).run_for_page(
        db=None,
        page=page,
        pipeline_run_id=pipeline_run_id,
    )

    assert result["reused_existing"] is True
    assert repo.mark_not_current_calls == []
    assert repo.created_files == []
    assert save_calls == []


@pytest.mark.asyncio
async def test_run_for_page_overwrites_current_inpaint_when_outputs_differ(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.utils.storage.settings", SimpleNamespace(storage_root_path=tmp_path))

    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    pipeline_run_id = uuid.uuid4()

    source_relative = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/original.png"
    source_path = tmp_path / source_relative
    source_path.parent.mkdir(parents=True, exist_ok=True)

    source_image = np.full((32, 32, 3), 255, dtype=np.uint8)
    source_image[8:24, 8:24] = 0
    assert cv2.imwrite(str(source_path), source_image)

    text_region = SimpleNamespace(
        id="t1",
        region_kind="text",
        bbox_json=[10.0, 10.0, 22.0, 22.0],
        polygon_json=[[1.0, 1.0], [5.0, 1.0], [5.0, 5.0], [1.0, 5.0]],
        parent_region_id=None,
        confidence=0.2,
        origin="mask_inference",
    )

    # Existing artifacts intentionally differ from generated results.
    existing_inpaint_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/existing/page.png"
    existing_mask_rel = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/artifacts/inpainted/existing/erasure_mask.png"
    existing_inpaint_path = tmp_path / existing_inpaint_rel
    existing_mask_path = tmp_path / existing_mask_rel
    existing_inpaint_path.parent.mkdir(parents=True, exist_ok=True)
    existing_mask_path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(existing_inpaint_path), np.zeros((32, 32, 3), dtype=np.uint8))
    assert cv2.imwrite(str(existing_mask_path), np.zeros((32, 32), dtype=np.uint8))

    source_file = SimpleNamespace(file_path=source_relative, mime_type="image/png")
    current_inpainted_file = SimpleNamespace(file_path=existing_inpaint_rel)
    current_mask_file = SimpleNamespace(file_path=existing_mask_rel)

    repo = FakePageRepo(
        source_file=source_file,
        text_regions=[text_region],
        balloon_regions=[],
        current_inpainted=current_inpainted_file,
        current_mask=current_mask_file,
    )

    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        chapter=SimpleNamespace(project_id=project_id),
    )

    save_calls: list[str] = []

    async def fake_save_cv2_image(_image, relative_path):
        save_calls.append(str(relative_path))
        return tmp_path / relative_path

    monkeypatch.setattr("app.services.inpaint_page_service.save_cv2_image", fake_save_cv2_image)

    result = await InpaintPageService(page_repo=repo).run_for_page(
        db=None,
        page=page,
        pipeline_run_id=pipeline_run_id,
    )

    assert result["reused_existing"] is False
    assert result["overwrote_existing_files"] is True
    assert len(save_calls) == 2
    assert all("/artifacts/inpainted/" in path for path in save_calls)
    assert all("/run_" not in path for path in save_calls)
    assert repo.mark_not_current_calls == []
    assert len(repo.created_files) == 0
