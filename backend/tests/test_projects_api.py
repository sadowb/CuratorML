from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.api.dependencies import get_db, get_project_service
from app.schemas.chapter import ChapterCreateRequest, ChapterOut
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectEntryOut,
    ProjectListItem,
    ProjectOut,
    ProjectWithChaptersOut,
)


async def fake_db_dependency():
    yield object()


class FakeProjectService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.project_id = uuid.uuid4()
        self.chapter_id = uuid.uuid4()
        self.page_id = uuid.uuid4()
        self.deleted = False

        self.project_out = ProjectOut(
            id=self.project_id,
            user_id=None,
            name="Demo Project",
            source_language="ja",
            target_language="en",
            reading_direction="LTR",
            project_status="active",
            context="context",
            enable_ocr=True,
            require_qc=True,
            created_at=now,
            updated_at=now,
        )
        self.chapter_out = ChapterOut(
            id=self.chapter_id,
            project_id=self.project_id,
            title="Chapter 1",
            chapter_number=1,
            chapter_status="active",
            created_at=now,
            updated_at=now,
        )

    def _ensure_exists(self, project_id: uuid.UUID) -> None:
        if self.deleted or project_id != self.project_id:
            raise LookupError("Project not found")

    async def create_project_with_initial_chapter(
        self,
        _db,
        _payload: ProjectCreateRequest,
    ) -> ProjectCreateResponse:
        return ProjectCreateResponse(project=self.project_out, chapter=self.chapter_out)

    async def list_projects_with_stats(self, _db) -> list[ProjectListItem]:
        if self.deleted:
            return []
        return [ProjectListItem(**self.project_out.model_dump(), chapter_count=1, page_count=3)]

    async def get_project_with_chapters(self, _db, project_id: uuid.UUID) -> ProjectWithChaptersOut:
        self._ensure_exists(project_id)
        return ProjectWithChaptersOut(project=self.project_out, chapters=[self.chapter_out])

    async def get_project_entry(self, _db, project_id: uuid.UUID) -> ProjectEntryOut:
        self._ensure_exists(project_id)
        return ProjectEntryOut(
            project_id=project_id,
            chapter_id=self.chapter_id,
            page_id=self.page_id,
            editor_url=f"/editor/{project_id}/{self.page_id}",
            upload_url=f"/projects/{project_id}/upload?chapterId={self.chapter_id}",
            reason="editor_ready",
        )

    async def create_chapter(self, _db, project_id: uuid.UUID, payload: ChapterCreateRequest) -> ChapterOut:
        self._ensure_exists(project_id)
        return ChapterOut(
            id=uuid.uuid4(),
            project_id=project_id,
            title=payload.title,
            chapter_number=payload.chapter_number,
            chapter_status="active",
            created_at=self.chapter_out.created_at,
            updated_at=self.chapter_out.updated_at,
        )

    async def list_project_chapters(self, _db, project_id: uuid.UUID) -> list[ChapterOut]:
        self._ensure_exists(project_id)
        return [self.chapter_out]

    async def delete_project(self, _db, project_id: uuid.UUID) -> None:
        self._ensure_exists(project_id)
        self.deleted = True


def test_projects_contract_endpoints(client, test_app) -> None:
    service = FakeProjectService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_project_service] = lambda: service

    create_payload = {
        "name": "Demo Project",
        "source_language": "ja",
        "target_language": "en",
        "reading_direction": "LTR",
        "chapter_title": "Chapter 1",
        "chapter_number": 1,
        "estimated_pages": 10,
        "context": "context",
        "enable_ocr": True,
        "require_qc": True,
    }
    created = client.post("/api/v1/projects", json=create_payload)
    assert created.status_code == 201
    created_body = created.json()
    assert "project" in created_body and "chapter" in created_body
    project_id = created_body["project"]["id"]

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body and {"chapter_count", "page_count"}.issubset(listed_body[0].keys())

    project = client.get(f"/api/v1/projects/{project_id}")
    assert project.status_code == 200
    assert {"project", "chapters"} == set(project.json().keys())

    entry = client.get(f"/api/v1/projects/{project_id}/entry")
    assert entry.status_code == 200
    entry_body = entry.json()
    assert entry_body["reason"] == "editor_ready"
    assert entry_body["editor_url"] is not None

    chapter = client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"title": "Chapter 2", "chapter_number": 2},
    )
    assert chapter.status_code == 201
    assert chapter.json()["chapter_number"] == 2

    chapters = client.get(f"/api/v1/projects/{project_id}/chapters")
    assert chapters.status_code == 200
    assert len(chapters.json()) == 1

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204


def test_projects_not_found_mapping(client, test_app) -> None:
    service = FakeProjectService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_project_service] = lambda: service

    missing_id = uuid.uuid4()
    response = client.get(f"/api/v1/projects/{missing_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
