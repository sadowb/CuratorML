from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from app.api.dependencies import get_chapter_service, get_db, get_page_service, get_project_service
from app.schemas.chapter import ChapterOut
from app.schemas.page import (
    PageDetailOut,
    PageFileOut,
    PageSummaryOut,
    PageTextOut,
    PageUploadItemOut,
    PageUploadResponse,
)
from app.schemas.project import ProjectCreateResponse, ProjectOut


async def fake_db_dependency():
    yield object()


class FakeProjectService:
    def __init__(self, project_id: uuid.UUID, chapter_id: uuid.UUID, now: datetime) -> None:
        self.project_id = project_id
        self.chapter_id = chapter_id
        self.now = now

    async def create_project_with_initial_chapter(self, _db, _payload) -> ProjectCreateResponse:
        return ProjectCreateResponse(
            project=ProjectOut(
                id=self.project_id,
                user_id=None,
                name="Smoke Project",
                source_language="ja",
                target_language="en",
                reading_direction="LTR",
                project_status="active",
                context=None,
                enable_ocr=True,
                require_qc=True,
                created_at=self.now,
                updated_at=self.now,
            ),
            chapter=ChapterOut(
                id=self.chapter_id,
                project_id=self.project_id,
                title="Chapter 1",
                chapter_number=1,
                chapter_status="active",
                created_at=self.now,
                updated_at=self.now,
            ),
        )


class FakeChapterService:
    def __init__(self, project_id: uuid.UUID, chapter_id: uuid.UUID, page_id: uuid.UUID, now: datetime) -> None:
        self.project_id = project_id
        self.chapter_id = chapter_id
        self.page_id = page_id
        self.now = now

    async def upload_pages(self, _db, chapter_id: uuid.UUID, _files) -> PageUploadResponse:
        if chapter_id != self.chapter_id:
            raise LookupError("Chapter not found")
        page = PageSummaryOut(
            id=self.page_id,
            chapter_id=self.chapter_id,
            page_number=1,
            current_stage="uploaded",
            review_status="pending",
            created_at=self.now,
            updated_at=self.now,
            original_file_url=f"/api/v1/storage/{self.project_id}/{self.chapter_id}/{self.page_id}/original",
        )
        page_file = PageFileOut(
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
            url=page.original_file_url,
        )
        return PageUploadResponse(items=[PageUploadItemOut(page=page, file=page_file)])


class FakePageService:
    def __init__(self, project_id: uuid.UUID, chapter_id: uuid.UUID, page_id: uuid.UUID, now: datetime) -> None:
        self.project_id = project_id
        self.chapter_id = chapter_id
        self.page_id = page_id
        self.now = now

    async def get_page_detail(self, _db, page_id: uuid.UUID) -> PageDetailOut:
        if page_id != self.page_id:
            raise LookupError("Page not found")
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
            url=f"/api/v1/storage/{self.project_id}/{self.chapter_id}/{self.page_id}/original",
        )
        text_out = PageTextOut(
            id=uuid.uuid4(),
            region_id=uuid.uuid4(),
            pipeline_run_id=None,
            ocr_text_raw="raw",
            ocr_text_corrected="corrected",
            ocr_confidence=0.9,
            context_notes=None,
            translation_draft=None,
            translation_corrected=None,
            display_text_final=None,
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
                regions=[],
        )


def test_health_and_core_smoke_flow(client, test_app) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()

    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_project_service] = lambda: FakeProjectService(project_id, chapter_id, now)
    test_app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(project_id, chapter_id, page_id, now)
    test_app.dependency_overrides[get_page_service] = lambda: FakePageService(project_id, chapter_id, page_id, now)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    create = client.post(
        "/api/v1/projects",
        json={
            "name": "Smoke Project",
            "source_language": "ja",
            "target_language": "en",
            "reading_direction": "LTR",
            "chapter_title": "Chapter 1",
            "chapter_number": 1,
            "context": None,
            "enable_ocr": True,
            "require_qc": True,
        },
    )
    assert create.status_code == 201
    created_body = create.json()
    created_chapter_id = created_body["chapter"]["id"]

    upload = client.post(
        f"/api/v1/chapters/{created_chapter_id}/pages/upload",
        files=[("files", ("p1.jpg", io.BytesIO(b"fake-image"), "image/jpeg"))],
    )
    assert upload.status_code == 201
    uploaded_page_id = upload.json()["items"][0]["page"]["id"]

    detail = client.get(f"/api/v1/pages/{uploaded_page_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["files"]
    assert detail_body["texts"]
