from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.api.dependencies import get_db, get_translation_memory_service


async def fake_db_dependency():
    yield object()


class FakeMemoryService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.project_id = uuid.uuid4()
        self.entry_id = uuid.uuid4()
        self.entry = {
            "id": self.entry_id,
            "project_id": self.project_id,
            "entry_type": "character",
            "source_term": "ゾロ",
            "preferred_translation": "Zoro",
            "scope_chapter": None,
            "aliases": ["ゾロー"],
            "notes": None,
            "created_at": now,
            "updated_at": now,
        }

    async def create_entry(self, _db, *, project_id: uuid.UUID, payload):  # noqa: ANN001
        return type("Entry", (), {**self.entry, "project_id": project_id})()

    async def create_entries_batch(self, _db, *, project_id: uuid.UUID, payloads):  # noqa: ANN001
        created = [
            type("Entry", (), {**self.entry, "project_id": project_id, "source_term": payload.source_term})()
            for payload in payloads
        ]
        return created, []

    async def list_entries(
        self,
        _db,
        *,
        project_id: uuid.UUID,
        entry_type: str | None = None,
        scope_chapter: int | None = None,
        q: str | None = None,
    ):
        del entry_type, scope_chapter, q
        return [type("Entry", (), {**self.entry, "project_id": project_id})()]

    async def update_entry(self, _db, *, project_id: uuid.UUID, entry_id: uuid.UUID, payload):  # noqa: ANN001
        if entry_id != self.entry_id:
            raise LookupError("Memory entry not found")
        updated = dict(self.entry)
        if payload.preferred_translation:
            updated["preferred_translation"] = payload.preferred_translation
        updated["project_id"] = project_id
        return type("Entry", (), updated)()

    async def delete_entry(self, _db, *, project_id: uuid.UUID, entry_id: uuid.UUID):  # noqa: ANN001
        if project_id != self.project_id or entry_id != self.entry_id:
            raise LookupError("Memory entry not found")


def test_memory_crud_endpoints(client, test_app) -> None:
    service = FakeMemoryService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_translation_memory_service] = lambda: service

    create_resp = client.post(
        f"/api/v1/projects/{service.project_id}/memory/entries",
        json={
            "entry_type": "character",
            "source_term": "ゾロ",
            "preferred_translation": "Zoro",
            "aliases": ["ゾロー"],
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["source_term"] == "ゾロ"

    list_resp = client.get(f"/api/v1/projects/{service.project_id}/memory/entries")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    patch_resp = client.patch(
        f"/api/v1/projects/{service.project_id}/memory/entries/{service.entry_id}",
        json={"preferred_translation": "ZORO"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["preferred_translation"] == "ZORO"

    delete_resp = client.delete(
        f"/api/v1/projects/{service.project_id}/memory/entries/{service.entry_id}"
    )
    assert delete_resp.status_code == 204


def test_memory_delete_not_found_mapping(client, test_app) -> None:
    service = FakeMemoryService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_translation_memory_service] = lambda: service

    delete_resp = client.delete(
        f"/api/v1/projects/{service.project_id}/memory/entries/{uuid.uuid4()}"
    )
    assert delete_resp.status_code == 404
    assert delete_resp.json()["detail"] == "Memory entry not found"


def test_memory_batch_create_endpoint(client, test_app) -> None:
    service = FakeMemoryService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_translation_memory_service] = lambda: service

    batch_resp = client.post(
        f"/api/v1/projects/{service.project_id}/memory/entries/batch",
        json={
            "entries": [
                {
                    "entry_type": "character",
                    "source_term": "ゾロ",
                    "preferred_translation": "Zoro",
                    "aliases": [],
                },
                {
                    "entry_type": "place",
                    "source_term": "ワノ国",
                    "preferred_translation": "Wano Country",
                    "aliases": [],
                },
            ]
        },
    )
    assert batch_resp.status_code == 201
    payload = batch_resp.json()
    assert len(payload["created"]) == 2
    assert payload["failed"] == []
