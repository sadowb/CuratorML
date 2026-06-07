from __future__ import annotations

import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.chapter_repository import ChapterRepository
from app.repositories.page_repository import PageRepository
from app.schemas.page import PaginatedPageSummaryOut, PageUploadResponse
from app.services.response_mapper import map_paginated_page_summaries, map_page_upload_response
from app.services.upload_service import UploadService


class ChapterService:
    def __init__(
        self,
        chapter_repo: ChapterRepository | None = None,
        page_repo: PageRepository | None = None,
        upload_service: UploadService | None = None,
    ) -> None:
        self.chapter_repo = chapter_repo or ChapterRepository()
        self.page_repo = page_repo or PageRepository()
        self.upload_service = upload_service or UploadService(chapter_repo=self.chapter_repo, page_repo=self.page_repo)

    async def upload_pages(
        self,
        db: AsyncSession,
        chapter_id: uuid.UUID,
        files: list[UploadFile],
    ) -> PageUploadResponse:
        chapter = await self.chapter_repo.get_by_id(db, chapter_id)
        if chapter is None:
            raise LookupError("Chapter not found")

        records = await self.upload_service.upload_pages(db, chapter_id, files)
        return map_page_upload_response(records, project_id=chapter.project_id, chapter_id=chapter_id)

    async def list_pages(
        self,
        db: AsyncSession,
        chapter_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
    ) -> PaginatedPageSummaryOut:
        chapter = await self.chapter_repo.get_by_id(db, chapter_id)
        if chapter is None:
            raise LookupError("Chapter not found")

        page_items, total = await self.page_repo.list_by_chapter_paginated(
            db,
            chapter_id,
            page=page,
            page_size=page_size,
        )
        return map_paginated_page_summaries(
            page_items,
            total=total,
            page=max(page, 1),
            page_size=max(min(page_size, 200), 1),
            project_id=chapter.project_id,
        )
