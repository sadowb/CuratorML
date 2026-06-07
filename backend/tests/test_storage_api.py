from __future__ import annotations

import uuid
from pathlib import Path

from app.api.dependencies import get_db, get_storage_service


async def fake_db_dependency():
    yield object()


class FakeStorageService:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path

    async def resolve_page_file(
        self,
        _db,
        *,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID,
        page_id: uuid.UUID,
        file_kind: str,
    ):
        if file_kind == "missing":
            raise LookupError("File not found")
        if file_kind == "invalid":
            raise ValueError("Invalid file path")
        if self.file_path is None:
            raise LookupError("File missing on disk")
        return self.file_path, "image/jpeg"


def test_storage_success_contract(client, test_app, tmp_path) -> None:
    file_path = tmp_path / "page.jpg"
    file_path.write_bytes(b"image-bytes")

    service = FakeStorageService(file_path=file_path)
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_storage_service] = lambda: service

    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    response = client.get(f"/api/v1/storage/{project_id}/{chapter_id}/{page_id}/original")
    assert response.status_code == 200
    assert response.content == b"image-bytes"


def test_storage_not_found_mapping(client, test_app) -> None:
    service = FakeStorageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_storage_service] = lambda: service

    response = client.get(f"/api/v1/storage/{uuid.uuid4()}/{uuid.uuid4()}/{uuid.uuid4()}/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_storage_invalid_path_mapping(client, test_app) -> None:
    service = FakeStorageService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_storage_service] = lambda: service

    response = client.get(f"/api/v1/storage/{uuid.uuid4()}/{uuid.uuid4()}/{uuid.uuid4()}/invalid")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file path"
