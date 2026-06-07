from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.page_region import PageRegionPatchRequest
from app.services.ml.yolo_inference_service import _apply_text_mask_dilation, _filter_duplicate_panels
from app.services.page_service import PageService


class FakeDbSession:
    def __init__(self) -> None:
        self.commits = 0
        self.refreshed: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, model: object) -> None:
        self.refreshed.append(model)


class FakePageRepo:
    def __init__(self, *, page: object | None, region: object | None) -> None:
        self._page = page
        self._region = region

    async def get_by_id(self, _db, _page_id: uuid.UUID):
        return self._page

    async def get_region_by_id(self, _db, _region_id: uuid.UUID):
        return self._region


def build_region(*, page_id: uuid.UUID) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        page_id=page_id,
        parent_region_id=None,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="text",
        polygon_json=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
        bbox_json=[0.0, 0.0, 10.0, 10.0],
        confidence=0.9,
        reading_order=None,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_patch_page_region_persists_and_marks_user_edit() -> None:
    page_id = uuid.uuid4()
    region = build_region(page_id=page_id)
    service = PageService(page_repo=FakePageRepo(page=object(), region=region))
    db = FakeDbSession()

    updated = await service.patch_page_region(
        db,
        page_id,
        region.id,
        PageRegionPatchRequest(polygon_json=[[1.0, 1.0], [11.0, 1.0], [11.0, 11.0], [1.0, 11.0]]),
    )

    assert db.commits == 1
    assert db.refreshed == [region]
    assert region.origin == "user_edited"
    assert region.polygon_json[0] == [1.0, 1.0]
    assert updated.origin == "user_edited"
    assert updated.polygon_json is not None


@pytest.mark.asyncio
async def test_patch_page_region_raises_when_page_missing() -> None:
    page_id = uuid.uuid4()
    region = build_region(page_id=page_id)
    service = PageService(page_repo=FakePageRepo(page=None, region=region))
    db = FakeDbSession()

    with pytest.raises(LookupError, match="Page not found"):
        await service.patch_page_region(
            db,
            page_id,
            region.id,
            PageRegionPatchRequest(is_active=False),
        )


@pytest.mark.asyncio
async def test_patch_page_region_raises_when_region_missing() -> None:
    page_id = uuid.uuid4()
    service = PageService(page_repo=FakePageRepo(page=object(), region=None))
    db = FakeDbSession()

    with pytest.raises(LookupError, match="Region not found"):
        await service.patch_page_region(
            db,
            page_id,
            uuid.uuid4(),
            PageRegionPatchRequest(is_active=False),
        )


@pytest.mark.asyncio
async def test_patch_page_region_raises_when_region_mismatch() -> None:
    page_id = uuid.uuid4()
    region = build_region(page_id=uuid.uuid4())
    service = PageService(page_repo=FakePageRepo(page=object(), region=region))
    db = FakeDbSession()

    with pytest.raises(ValueError, match="Region does not belong to the provided page"):
        await service.patch_page_region(
            db,
            page_id,
            region.id,
            PageRegionPatchRequest(is_active=False),
        )


def test_apply_text_mask_dilation_expands_bbox_without_replacing_existing_masks() -> None:
    text_detection = {
        "id": 1,
        "region_kind": "text",
        "box": [10.0, 20.0, 30.0, 40.0],
        "conf": 0.9,
        "mask": [[10.0, 20.0], [30.0, 20.0], [30.0, 40.0], [10.0, 40.0]],
    }
    balloon_detection = {
        "id": 2,
        "region_kind": "balloon",
        "box": [50.0, 60.0, 90.0, 110.0],
        "conf": 0.88,
        "mask": [[50.0, 60.0], [90.0, 60.0], [90.0, 110.0], [50.0, 110.0]],
    }
    panel_detection = {
        "id": 3,
        "region_kind": "panel",
        "box": [100.0, 120.0, 180.0, 220.0],
        "conf": 0.8,
        "mask": [[100.0, 120.0], [180.0, 120.0], [180.0, 220.0], [100.0, 220.0]],
    }

    dilated_text = _apply_text_mask_dilation(text_detection)
    dilated_balloon = _apply_text_mask_dilation(balloon_detection)
    untouched_panel = _apply_text_mask_dilation(panel_detection)

    assert dilated_text["box"][0] < text_detection["box"][0]
    assert dilated_text["box"][1] < text_detection["box"][1]
    assert dilated_text["box"][2] > text_detection["box"][2]
    assert dilated_text["box"][3] > text_detection["box"][3]
    assert dilated_text["mask"] == text_detection["mask"]
    assert dilated_balloon["box"][0] < balloon_detection["box"][0]
    assert dilated_balloon["box"][1] < balloon_detection["box"][1]
    assert dilated_balloon["box"][2] > balloon_detection["box"][2]
    assert dilated_balloon["box"][3] > balloon_detection["box"][3]
    assert dilated_balloon["mask"] == balloon_detection["mask"]
    assert untouched_panel == panel_detection


def test_filter_duplicate_panels_removes_overlapping_lower_confidence_panel() -> None:
    detections = [
        {
            "id": 10,
            "region_kind": "panel",
            "box": [0.0, 0.0, 100.0, 100.0],
            "conf": 0.95,
            "mask": [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]],
        },
        {
            "id": 11,
            "region_kind": "panel",
            "box": [5.0, 5.0, 95.0, 95.0],
            "conf": 0.80,
            "mask": [[5.0, 5.0], [95.0, 5.0], [95.0, 95.0], [5.0, 95.0]],
        },
        {
            "id": 12,
            "region_kind": "panel",
            "box": [150.0, 0.0, 250.0, 100.0],
            "conf": 0.70,
            "mask": [[150.0, 0.0], [250.0, 0.0], [250.0, 100.0], [150.0, 100.0]],
        },
        {
            "id": 13,
            "region_kind": "text",
            "box": [300.0, 20.0, 360.0, 60.0],
            "conf": 0.91,
            "mask": [[300.0, 20.0], [360.0, 20.0], [360.0, 60.0], [300.0, 60.0]],
        },
    ]

    filtered = _filter_duplicate_panels(detections)
    kept_ids = [detection["id"] for detection in filtered]

    assert kept_ids == [10, 12, 13]
