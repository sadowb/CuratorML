from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.page import Page
from app.models.project import Project
from app.repositories.base_repository import RepositoryBase


class ProjectRepository(RepositoryBase):
    async def create(self, db: AsyncSession, project: Project) -> Project:
        return await self._create(db, project)

    async def get_by_id(self, db: AsyncSession, project_id: uuid.UUID) -> Project | None:
        stmt = (
            select(Project)
            .options(selectinload(Project.chapters))
            .where(Project.id == project_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_stats(self, db: AsyncSession) -> list[tuple[Project, int, int]]:
        stmt = (
            select(
                Project,
                func.count(func.distinct(Chapter.id)).label("chapter_count"),
                func.count(func.distinct(Page.id)).label("page_count"),
            )
            .outerjoin(Chapter, Chapter.project_id == Project.id)
            .outerjoin(Page, Page.chapter_id == Chapter.id)
            .group_by(Project.id)
            .order_by(Project.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def delete_by_id(self, db: AsyncSession, project_id: uuid.UUID) -> bool:
        project = await self.get_by_id(db, project_id)
        if project is None:
            return False
        await self._delete(db, project)
        return True
