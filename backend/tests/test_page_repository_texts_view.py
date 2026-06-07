from __future__ import annotations

import uuid

import pytest

from app.repositories.page_repository import PageRepository


class FakeMappingResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return FakeMappingResult(self._rows)


class FakeDbSession:
    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    async def execute(self, stmt, params=None):
        self.calls.append((stmt, params))
        return FakeExecuteResult(self._rows)


@pytest.mark.asyncio
async def test_get_page_text_rows_queries_view_with_expected_filter_and_order() -> None:
    page_id = uuid.uuid4()
    rows = [
        {
            "page_text_id": None,
            "region_id": uuid.uuid4(),
            "page_id": page_id,
            "reading_order": 2,
            "ocr_text_raw": "a",
            "ocr_text_corrected": "a2",
            "translation_draft": "t",
        }
    ]
    db = FakeDbSession(rows)

    repo = PageRepository()
    out = await repo.get_page_text_rows(db, page_id=page_id)

    assert out == rows
    assert len(db.calls) == 1

    stmt, params = db.calls[0]
    sql = str(stmt)
    assert "v_page_text_regions_active" in sql
    assert "ORDER BY reading_order ASC NULLS LAST, region_id" in sql
    assert params == {"page_id": str(page_id)}
