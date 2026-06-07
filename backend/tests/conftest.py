from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_app() -> FastAPI:
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    with TestClient(test_app) as api_client:
        yield api_client


async def fake_db_dependency():
    yield object()
