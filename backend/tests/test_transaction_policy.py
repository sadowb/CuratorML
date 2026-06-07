from __future__ import annotations

import pytest

from app.core import database


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, _exc_type, _exc, _tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_db_session_commits_once_on_success(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(database, "AsyncSessionFactory", FakeSessionFactory(session))

    generator = database.get_db_session()
    yielded_session = await anext(generator)
    assert yielded_session is session

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert session.commit_calls == 1
    assert session.rollback_calls == 0


@pytest.mark.asyncio
async def test_db_session_rolls_back_on_exception(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(database, "AsyncSessionFactory", FakeSessionFactory(session))

    generator = database.get_db_session()
    await anext(generator)

    with pytest.raises(RuntimeError):
        await generator.athrow(RuntimeError("boom"))

    assert session.commit_calls == 0
    assert session.rollback_calls == 1
