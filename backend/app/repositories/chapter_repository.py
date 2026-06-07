from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chapter import Chapter
from app.models.page import Page
from app.repositories.base_repository import RepositoryBase


class ChapterRepository(RepositoryBase):
    async def create(self, db: AsyncSession, chapter: Chapter) -> Chapter:
        return await self._create(db, chapter)

    async def list_by_project(self, db: AsyncSession, project_id: uuid.UUID) -> list[Chapter]:
        stmt = (
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, chapter_id: uuid.UUID, with_pages: bool = False) -> Chapter | None:
        stmt = select(Chapter).where(Chapter.id == chapter_id)
        if with_pages:
            stmt = stmt.options(selectinload(Chapter.pages).selectinload(Page.files))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
