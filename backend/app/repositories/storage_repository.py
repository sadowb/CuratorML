from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.page import Page
from app.models.page_file import PageFile
from app.models.project import Project


class StorageRepository:
    async def get_file_for_storage_path(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID,
        page_id: uuid.UUID,
        file_kind: str,
    ) -> PageFile | None:
        stmt = (
            select(PageFile)
            .join(Page, Page.id == PageFile.page_id)
            .join(Chapter, Chapter.id == Page.chapter_id)
            .join(Project, Project.id == Chapter.project_id)
            .where(
                Project.id == project_id,
                Chapter.id == chapter_id,
                Page.id == page_id,
                PageFile.file_kind == file_kind,
                PageFile.is_current.is_(True),
            )
            .order_by(PageFile.created_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()
