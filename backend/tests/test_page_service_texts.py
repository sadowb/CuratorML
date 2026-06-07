from __future__ import annotations

import uuid

import pytest

from app.services.page_service import PageService


class FakePageRepo:
    def __init__(self, *, page: object | None, rows: list[dict[str, object]]) -> None:
        self._page = page
        self._rows = rows

    async def get_by_id(self, _db, _page_id: uuid.UUID):
        return self._page

    async def get_page_text_rows(self, _db, *, page_id: uuid.UUID):
        return self._rows


@pytest.mark.asyncio
async def test_get_page_texts_raises_when_page_missing() -> None:
    page_id = uuid.uuid4()
    service = PageService(page_repo=FakePageRepo(page=None, rows=[]))

    with pytest.raises(LookupError, match="Page not found"):
        await service.get_page_texts(object(), page_id)


@pytest.mark.asyncio
async def test_get_page_texts_maps_rows_and_nullable_fields() -> None:
    page_id = uuid.uuid4()
    region_id = uuid.uuid4()
    service = PageService(
        page_repo=FakePageRepo(
            page=object(),
            rows=[
                {
                    "page_text_id": None,
                    "region_id": region_id,
                    "page_id": page_id,
                    "reading_order": None,
                    "ocr_text_raw": None,
                    "ocr_text_corrected": "fixed",
                    "translation_draft": None,
                }
            ],
        )
    )

    out = await service.get_page_texts(object(), page_id)

    assert out.page_id == page_id
    assert len(out.items) == 1
    assert out.items[0].page_text_id is None
    assert out.items[0].region_id == region_id
    assert out.items[0].reading_order is None
    assert out.items[0].ocr_text_raw is None
    assert out.items[0].ocr_text_corrected == "fixed"
