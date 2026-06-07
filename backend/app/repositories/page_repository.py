from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.page import Page
from app.models.page_file import PageFile
from app.models.page_region import PageRegion
from app.models.page_text import PageText
from app.models.chapter import Chapter
from app.repositories.base_repository import RepositoryBase


class PageRepository(RepositoryBase):
    async def create(self, db: AsyncSession, page: Page) -> Page:
        return await self._create(db, page)

    async def create_file(self, db: AsyncSession, page_file: PageFile) -> PageFile:
        return await self._create(db, page_file)

    async def next_page_number(self, db: AsyncSession, chapter_id: uuid.UUID) -> int:
        stmt = select(func.max(Page.page_number)).where(Page.chapter_id == chapter_id)
        result = await db.execute(stmt)
        max_value = result.scalar_one_or_none()
        return (max_value or 0) + 1

    async def list_by_chapter(self, db: AsyncSession, chapter_id: uuid.UUID) -> list[Page]:
        stmt = (
            select(Page)
            .options(selectinload(Page.files), selectinload(Page.chapter))
            .where(Page.chapter_id == chapter_id)
            .order_by(Page.page_number.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_chapter_paginated(
        self,
        db: AsyncSession,
        chapter_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Page], int]:
        safe_page = max(page, 1)
        safe_page_size = max(min(page_size, 200), 1)

        total_stmt = select(func.count(Page.id)).where(Page.chapter_id == chapter_id)
        total_result = await db.execute(total_stmt)
        total = int(total_result.scalar_one() or 0)

        offset = (safe_page - 1) * safe_page_size
        stmt = (
            select(Page)
            .options(selectinload(Page.files), selectinload(Page.chapter))
            .where(Page.chapter_id == chapter_id)
            .order_by(Page.page_number.asc())
            .offset(offset)
            .limit(safe_page_size)
        )
        result = await db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, db: AsyncSession, page_id: uuid.UUID) -> Page | None:
        stmt = (
            select(Page)
            .options(
                selectinload(Page.files),
                selectinload(Page.chapter),
                selectinload(Page.regions).selectinload(PageRegion.texts),
            )
            .where(Page.id == page_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_current_file_by_kind(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        file_kind: str,
    ) -> PageFile | None:
        stmt = (
            select(PageFile)
            .where(
                PageFile.page_id == page_id,
                PageFile.file_kind == file_kind,
                PageFile.is_current.is_(True),
            )
            .order_by(PageFile.created_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_text_by_id(self, db: AsyncSession, text_id: uuid.UUID) -> PageText | None:
        stmt = (
            select(PageText)
            .options(selectinload(PageText.region))
            .where(PageText.id == text_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_region_by_id(self, db: AsyncSession, region_id: uuid.UUID) -> PageRegion | None:
        stmt = select(PageRegion).where(PageRegion.id == region_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_first_page_for_project(self, db: AsyncSession, project_id: uuid.UUID) -> Page | None:
        stmt = (
            select(Page)
            .join(Chapter, Chapter.id == Page.chapter_id)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number.asc(), Page.page_number.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_regions(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        *,
        kinds: list[str] | None = None,
    ) -> list[PageRegion]:
        stmt = (
            select(PageRegion)
            .options(selectinload(PageRegion.texts))
            .where(
                PageRegion.page_id == page_id,
                PageRegion.is_active.is_(True),
            )
        )
        if kinds:
            stmt = stmt.where(PageRegion.region_kind.in_(kinds))
        stmt = stmt.order_by(PageRegion.reading_order.asc().nullslast(), PageRegion.created_at.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_texts_for_region_ids(
        self,
        db: AsyncSession,
        region_ids: list[uuid.UUID],
    ) -> list[PageText]:
        if not region_ids:
            return []
        stmt = select(PageText).where(PageText.region_id.in_(region_ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_page_text(
        self,
        db: AsyncSession,
        *,
        region_id: uuid.UUID,
    ) -> PageText:
        stmt = select(PageText).where(PageText.region_id == region_id)
        result = await db.execute(stmt)
        page_text = result.scalar_one_or_none()
        if page_text is not None:
            return page_text

        page_text = PageText(region_id=region_id)
        db.add(page_text)
        await db.flush()
        return page_text

    async def mark_files_not_current(
        self,
        db: AsyncSession,
        *,
        page_id: uuid.UUID,
        file_kind: str,
    ) -> None:
        stmt = (
            update(PageFile)
            .where(
                PageFile.page_id == page_id,
                PageFile.file_kind == file_kind,
                PageFile.is_current.is_(True),
            )
            .values(is_current=False)
        )
        await db.execute(stmt)

    async def get_page_text_rows(
        self,
        db: AsyncSession,
        *,
        page_id: uuid.UUID,
    ) -> Sequence[RowMapping]:
        stmt = text(
            """
            SELECT
                page_text_id,
                region_id,
                page_id,
                reading_order,
                ocr_text_raw,
                ocr_text_corrected,
                translation_draft
            FROM public.v_page_text_regions_active
            WHERE page_id = :page_id
            ORDER BY reading_order ASC NULLS LAST, region_id
            """
        )
        result = await db.execute(stmt, {"page_id": str(page_id)})
        return result.mappings().all()
