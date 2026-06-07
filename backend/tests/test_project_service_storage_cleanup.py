from __future__ import annotations

import uuid

import pytest

from app.services.project_service import ProjectService


class FakeProjectRepository:
    def __init__(self, *, should_delete: bool) -> None:
        self.should_delete = should_delete

    async def delete_by_id(self, _db, _project_id: uuid.UUID) -> bool:
        return self.should_delete


@pytest.mark.asyncio
async def test_delete_project_triggers_storage_cleanup(monkeypatch) -> None:
    project_id = uuid.uuid4()
    called_with: list[uuid.UUID] = []

    def fake_cleanup(target_project_id: uuid.UUID) -> None:
        called_with.append(target_project_id)

    monkeypatch.setattr("app.services.project_service.remove_project_storage", fake_cleanup)
    service = ProjectService(project_repo=FakeProjectRepository(should_delete=True))

    await service.delete_project(db=object(), project_id=project_id)
    assert called_with == [project_id]


@pytest.mark.asyncio
async def test_delete_project_not_found_does_not_cleanup(monkeypatch) -> None:
    called = False

    def fake_cleanup(_project_id: uuid.UUID) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.services.project_service.remove_project_storage", fake_cleanup)
    service = ProjectService(project_repo=FakeProjectRepository(should_delete=False))

    with pytest.raises(LookupError, match="Project not found"):
        await service.delete_project(db=object(), project_id=uuid.uuid4())

    assert called is False
