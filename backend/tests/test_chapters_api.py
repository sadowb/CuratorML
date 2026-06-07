from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from app.api.dependencies import get_chapter_service, get_db
from app.schemas.page import (
    PageFileOut,
    PagePaginationOut,
    PageSummaryOut,
    PageUploadItemOut,
    PageUploadResponse,
    PaginatedPageSummaryOut,
)


async def fake_db_dependency():
    yield object()


class FakeChapterService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.chapter_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.page_id = uuid.uuid4()
        self.now = now

    def _ensure_exists(self, chapter_id: uuid.UUID) -> None:
        if chapter_id != self.chapter_id:
            raise LookupError("Chapter not found")

    async def upload_pages(self, _db, chapter_id: uuid.UUID, files) -> PageUploadResponse:
        self._ensure_exists(chapter_id)
        if not files:
            raise ValueError("At least one file is required")
        summary = PageSummaryOut(
            id=self.page_id,
            chapter_id=chapter_id,
            page_number=1,
            current_stage="uploaded",
            review_status="pending",
            created_at=self.now,
            updated_at=self.now,
            original_file_url=f"/api/v1/storage/{self.project_id}/{chapter_id}/{self.page_id}/original",
        )
        file_out = PageFileOut(
            id=uuid.uuid4(),
            page_id=self.page_id,
            pipeline_run_id=None,
            file_kind="original",
            file_path="project_a/chapter_b/page_1/original.jpg",
            mime_type="image/jpeg",
            width=None,
            height=None,
            is_current=True,
            created_at=self.now,
            url=summary.original_file_url,
        )
        return PageUploadResponse(items=[PageUploadItemOut(page=summary, file=file_out)])

    async def list_pages(
        self,
        _db,
        chapter_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
    ) -> PaginatedPageSummaryOut:
        self._ensure_exists(chapter_id)
        summary = PageSummaryOut(
            id=self.page_id,
            chapter_id=chapter_id,
            page_number=1,
            current_stage="uploaded",
            review_status="pending",
            created_at=self.now,
            updated_at=self.now,
            original_file_url=f"/api/v1/storage/{self.project_id}/{chapter_id}/{self.page_id}/original",
        )
        return PaginatedPageSummaryOut(
            items=[summary],
            pagination=PagePaginationOut(
                page=page,
                page_size=page_size,
                total=1,
                has_next=False,
                has_prev=False,
            ),
        )


def test_chapter_pages_upload_contract(client, test_app) -> None:
    service = FakeChapterService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_chapter_service] = lambda: service

    response = client.post(
        f"/api/v1/chapters/{service.chapter_id}/pages/upload",
        files=[("files", ("page-1.jpg", io.BytesIO(b"image-bytes"), "image/jpeg"))],
    )
    assert response.status_code == 201
    body = response.json()
    assert "items" in body and len(body["items"]) == 1
    assert "page" in body["items"][0] and "file" in body["items"][0]


def test_chapter_pages_list_contract(client, test_app) -> None:
    service = FakeChapterService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_chapter_service] = lambda: service

    response = client.get(f"/api/v1/chapters/{service.chapter_id}/pages?page=1&page_size=25")
    assert response.status_code == 200
    body = response.json()
    assert {"items", "pagination"} == set(body.keys())
    assert {"page", "page_size", "total", "has_next", "has_prev"} == set(body["pagination"].keys())


def test_chapter_not_found_mapping(client, test_app) -> None:
    service = FakeChapterService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_chapter_service] = lambda: service

    response = client.get(f"/api/v1/chapters/{uuid.uuid4()}/pages")
    assert response.status_code == 404
    assert response.json()["detail"] == "Chapter not found"
