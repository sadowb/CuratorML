from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.api.dependencies import get_db, get_page_service
from app.schemas.mask_inference import DetectionOut, MaskInferenceResponse
from app.schemas.page import (
    PageDetailOut,
    PageFileOut,
    PageInpaintResultOut,
    PageOcrResultOut,
    PageOcrTextOut,
    PageReadingOrderOut,
    PageTextsReadOut,
    PageTextReadItemOut,
    PageTextOut,
    ReadingOrderPanelOut,
)
from app.schemas.page_region import PageRegionOut
from app.services.job_dispatcher import job_dispatcher


async def fake_db_dependency():
    yield object()


class FakePageService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.page_id = uuid.uuid4()
        self.text_id = uuid.uuid4()
        self.region_id = uuid.uuid4()
        self.mismatch_region_id = uuid.uuid4()
        self.chapter_id = uuid.uuid4()
        self.now = now

    def _ensure_page(self, page_id: uuid.UUID) -> None:
        if page_id != self.page_id:
            raise LookupError("Page not found")

    async def get_page_detail(self, _db, page_id: uuid.UUID) -> PageDetailOut:
        self._ensure_page(page_id)
        file_out = PageFileOut(
            id=uuid.uuid4(),
            page_id=self.page_id,
            pipeline_run_id=None,
            file_kind="original",
            file_path="project/chapter/page/original.jpg",
            mime_type="image/jpeg",
            width=None,
            height=None,
            is_current=True,
            created_at=self.now,
            url=f"/api/v1/storage/{uuid.uuid4()}/{self.chapter_id}/{self.page_id}/original",
        )
        text_out = PageTextOut(
            id=self.text_id,
            region_id=self.region_id,
            pipeline_run_id=None,
            ocr_text_raw="raw",
            ocr_text_corrected="corrected",
            ocr_confidence=0.9,
            context_notes="context",
            translation_draft="draft",
            translation_corrected="final",
            display_text_final="display",
            translation_status="draft",
            created_at=self.now,
            updated_at=self.now,
        )
        return PageDetailOut(
            id=self.page_id,
            chapter_id=self.chapter_id,
            page_number=1,
            current_stage="uploaded",
            review_status="pending",
            created_at=self.now,
            updated_at=self.now,
            original_file_url=file_out.url,
            files=[file_out],
            texts=[text_out],
            regions=[self._region_out()],
        )

    def _region_out(self) -> PageRegionOut:
        return PageRegionOut(
            id=self.region_id,
            page_id=self.page_id,
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
            created_at=self.now,
            updated_at=self.now,
        )

    async def patch_page_text(self, _db, page_id: uuid.UUID, text_id: uuid.UUID, _payload) -> PageTextOut:
        self._ensure_page(page_id)
        if text_id != self.text_id:
            raise LookupError("Text block not found")
        return PageTextOut(
            id=self.text_id,
            region_id=self.region_id,
            pipeline_run_id=None,
            ocr_text_raw="raw",
            ocr_text_corrected="updated",
            ocr_confidence=0.92,
            context_notes="updated-context",
            translation_draft="draft",
            translation_corrected="updated-final",
            display_text_final="updated-display",
            translation_status="reviewed",
            created_at=self.now,
            updated_at=self.now,
        )

    async def run_mask_inference(self, _db, page_id: uuid.UUID) -> MaskInferenceResponse:
        self._ensure_page(page_id)
        return MaskInferenceResponse(
            pipeline_run_id=uuid.uuid4(),
            page_id=self.page_id,
            stage="mask_inference_completed",
            detections=[
                DetectionOut(
                    id=0,
                    region_kind="text",
                    box=[0.0, 0.0, 10.0, 10.0],
                    conf=0.9,
                    mask=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
                )
            ],
        )

    async def patch_page_region(self, _db, page_id: uuid.UUID, region_id: uuid.UUID, _payload) -> PageRegionOut:
        self._ensure_page(page_id)
        if region_id == self.mismatch_region_id:
            raise ValueError("Region does not belong to the provided page")
        if region_id != self.region_id:
            raise LookupError("Region not found")

        region = self._region_out().model_copy()
        region.polygon_json = [[1.0, 1.0], [11.0, 1.0], [11.0, 11.0], [1.0, 11.0]]
        region.origin = "user_edited"
        return region

    async def get_page_ocr_result(self, _db, page_id: uuid.UUID) -> PageOcrResultOut:
        self._ensure_page(page_id)
        return PageOcrResultOut(
            page_id=self.page_id,
            items=[
                PageOcrTextOut(
                    region_id=self.region_id,
                    reading_order=1,
                    ocr_text_raw="hello",
                    ocr_confidence=0.9,
                )
            ],
        )

    async def get_page_reading_order(self, _db, page_id: uuid.UUID) -> PageReadingOrderOut:
        self._ensure_page(page_id)
        return PageReadingOrderOut(
            page_id=self.page_id,
            panels=[ReadingOrderPanelOut(panel=self._region_out(), items=[self._region_out()])],
        )

    async def get_page_inpaint_result(self, _db, page_id: uuid.UUID) -> PageInpaintResultOut:
        self._ensure_page(page_id)
        return PageInpaintResultOut(
            page_id=self.page_id,
            file=PageFileOut(
                id=uuid.uuid4(),
                page_id=self.page_id,
                pipeline_run_id=None,
                file_kind="inpainted",
                file_path="project/chapter/page/inpainted.jpg",
                mime_type="image/jpeg",
                width=100,
                height=120,
                is_current=True,
                created_at=self.now,
                url=f"/api/v1/storage/{uuid.uuid4()}/{self.chapter_id}/{self.page_id}/inpainted",
            ),
        )

    async def get_page_texts(self, _db, page_id: uuid.UUID) -> PageTextsReadOut:
        self._ensure_page(page_id)
        return PageTextsReadOut(
            page_id=self.page_id,
            items=[
                PageTextReadItemOut(
                    page_text_id=self.text_id,
                    region_id=self.region_id,
                    page_id=self.page_id,
                    reading_order=1,
                    ocr_text_raw="raw",
                    ocr_text_corrected="corrected",
                    translation_draft="draft",
                )
            ],
        )


def test_page_detail_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{service.page_id}")
    assert response.status_code == 200
    body = response.json()
    assert {"files", "texts", "regions", "original_file_url"}.issubset(body.keys())
    assert body["texts"] and body["files"]


def test_page_text_patch_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.patch(
        f"/api/v1/pages/{service.page_id}/texts/{service.text_id}",
        json={"display_text_final": "patched"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_text_final"] == "updated-display"


def test_page_not_found_mapping(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Page not found"


def test_mask_inference_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.post(f"/api/v1/pages/{service.page_id}/mask-inference")
    assert response.status_code == 200
    body = response.json()
    assert body["page_id"] == str(service.page_id)
    assert body["stage"] == "mask_inference_completed"
    assert body["detections"]


def test_page_region_patch_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.patch(
        f"/api/v1/pages/{service.page_id}/regions/{service.region_id}",
        json={"polygon_json": [[1, 1], [11, 1], [11, 11], [1, 11]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["origin"] == "user_edited"
    assert body["polygon_json"][0] == [1.0, 1.0]


def test_page_region_patch_not_found_mapping(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.patch(
        f"/api/v1/pages/{service.page_id}/regions/{uuid.uuid4()}",
        json={"is_active": False},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Region not found"


def test_page_region_patch_mismatch_mapping(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.patch(
        f"/api/v1/pages/{service.page_id}/regions/{service.mismatch_region_id}",
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Region does not belong to the provided page"


def test_get_ocr_result_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{service.page_id}/ocr")
    assert response.status_code == 200
    body = response.json()
    assert body["page_id"] == str(service.page_id)
    assert body["items"][0]["ocr_text_raw"] == "hello"


def test_get_reading_order_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{service.page_id}/reading-order")
    assert response.status_code == 200
    body = response.json()
    assert body["page_id"] == str(service.page_id)
    assert body["panels"]


def test_get_inpaint_result_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{service.page_id}/inpaint")
    assert response.status_code == 200
    body = response.json()
    assert body["page_id"] == str(service.page_id)
    assert body["file"]["file_kind"] == "inpainted"


def test_get_page_texts_contract(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{service.page_id}/texts")
    assert response.status_code == 200
    body = response.json()
    assert body["page_id"] == str(service.page_id)
    assert len(body["items"]) == 1
    assert body["items"][0]["region_id"] == str(service.region_id)
    assert body["items"][0]["translation_draft"] == "draft"


def test_get_page_texts_not_found_mapping(client, test_app) -> None:
    service = FakePageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{uuid.uuid4()}/texts")
    assert response.status_code == 404
    assert response.json()["detail"] == "Page not found"


def test_get_page_texts_empty_items_contract(client, test_app) -> None:
    service = FakePageService()

    async def _empty_page_texts(_db, page_id: uuid.UUID) -> PageTextsReadOut:
        service._ensure_page(page_id)
        return PageTextsReadOut(page_id=service.page_id, items=[])

    service.get_page_texts = _empty_page_texts  # type: ignore[method-assign]
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_page_service] = lambda: service

    response = client.get(f"/api/v1/pages/{service.page_id}/texts")
    assert response.status_code == 200
    assert response.json() == {"page_id": str(service.page_id), "items": []}


def test_stage_specific_submit_routes_removed(client, test_app) -> None:
    page_id = uuid.uuid4()
    test_app.dependency_overrides[get_db] = fake_db_dependency

    assert client.post(f"/api/v1/pages/{page_id}/ocr").status_code == 405
    assert client.post(f"/api/v1/pages/{page_id}/reading-order").status_code == 405
    assert client.post(f"/api/v1/pages/{page_id}/inpaint").status_code == 405


def test_submit_generic_job_contract(client, test_app, monkeypatch) -> None:
    page_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async def fake_submit(_db, received_page_id, stage):
        assert received_page_id == page_id
        assert stage == "ocr"
        return type("Run", (), {"id": job_id, "page_id": page_id, "stage": stage, "status": "pending"})()

    test_app.dependency_overrides[get_db] = fake_db_dependency
    monkeypatch.setattr(job_dispatcher, "submit", fake_submit)

    response = client.post(
        f"/api/v1/pages/{page_id}/jobs",
        json={"stage": "ocr"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": str(job_id),
        "page_id": str(page_id),
        "stage": "ocr",
        "status": "pending",
    }
    assert response.headers["location"].endswith(f"/api/v1/jobs/{job_id}")
    assert response.headers["retry-after"] == "2"
