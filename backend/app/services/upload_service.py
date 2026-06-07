from __future__ import annotations

import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.page_file import PageFile
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.page_repository import PageRepository
from app.utils.image_validator import validate_image_filename
from app.utils.storage import build_page_storage_path, save_upload_file


class UploadService:
    def __init__(
        self,
        chapter_repo: ChapterRepository | None = None,
        page_repo: PageRepository | None = None,
    ) -> None:
        self.chapter_repo = chapter_repo or ChapterRepository()
        self.page_repo = page_repo or PageRepository()

    async def upload_pages(
        self,
        db: AsyncSession,
        chapter_id: uuid.UUID,
        files: list[UploadFile],
    ) -> list[tuple[Page, PageFile]]:
        chapter = await self.chapter_repo.get_by_id(db, chapter_id)
        if chapter is None:
            raise ValueError("Chapter not found")

        if not files:
            raise ValueError("At least one file is required")

        next_page_number = await self.page_repo.next_page_number(db, chapter_id)
        created_records: list[tuple[Page, PageFile]] = []

        for file_obj in files:
            suffix = validate_image_filename(file_obj.filename)
            page = Page(
                chapter_id=chapter_id,
                page_number=next_page_number,
                current_stage="uploaded",
                review_status="pending",
            )
            page = await self.page_repo.create(db, page)

            relative_path = build_page_storage_path(
                project_id=str(chapter.project_id),
                chapter_id=str(chapter_id),
                page_id=str(page.id),
                filename_suffix=suffix,
                file_kind="original",
            )
            await save_upload_file(file_obj, relative_path)

            page_file = PageFile(
                page_id=page.id,
                pipeline_run_id=None,
                file_kind="original",
                file_path=str(relative_path),
                mime_type=file_obj.content_type or "application/octet-stream",
                width=None,
                height=None,
                is_current=True,
            )
            page_file = await self.page_repo.create_file(db, page_file)

            created_records.append((page, page_file))
            next_page_number += 1

        return created_records
