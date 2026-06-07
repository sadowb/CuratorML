from __future__ import annotations

import uuid

from sqlalchemy import Select, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.translation_memory_entry import TranslationMemoryEntry
from app.repositories.base_repository import RepositoryBase


class TranslationMemoryRepository(RepositoryBase):
    async def create(
        self,
        db: AsyncSession,
        entry: TranslationMemoryEntry,
    ) -> TranslationMemoryEntry:
        return await self._create(db, entry)

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> TranslationMemoryEntry | None:
        stmt = select(TranslationMemoryEntry).where(
            TranslationMemoryEntry.id == entry_id,
            TranslationMemoryEntry.project_id == project_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_project(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        entry_type: str | None = None,
        scope_chapter: int | None = None,
        q: str | None = None,
    ) -> list[TranslationMemoryEntry]:
        stmt: Select[tuple[TranslationMemoryEntry]] = select(TranslationMemoryEntry).where(
            TranslationMemoryEntry.project_id == project_id
        )
        if entry_type:
            stmt = stmt.where(TranslationMemoryEntry.entry_type == entry_type)
        if scope_chapter is not None:
            stmt = stmt.where(TranslationMemoryEntry.scope_chapter == scope_chapter)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    TranslationMemoryEntry.source_term.ilike(pattern),
                    TranslationMemoryEntry.preferred_translation.ilike(pattern),
                    TranslationMemoryEntry.notes.ilike(pattern),
                )
            )

        stmt = stmt.order_by(
            TranslationMemoryEntry.scope_chapter.asc().nullsfirst(),
            TranslationMemoryEntry.updated_at.desc(),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, db: AsyncSession, entry: TranslationMemoryEntry) -> None:
        await self._delete(db, entry)

    async def exact_match(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        candidate_terms: list[str],
        scope_chapter: int | None,
        limit: int,
    ) -> list[TranslationMemoryEntry]:
        if not candidate_terms:
            return []
        stmt = (
            select(TranslationMemoryEntry)
            .where(
                TranslationMemoryEntry.project_id == project_id,
                or_(
                    TranslationMemoryEntry.scope_chapter.is_(None),
                    TranslationMemoryEntry.scope_chapter == scope_chapter,
                ),
                or_(
                    TranslationMemoryEntry.normalized_source_term.in_(candidate_terms),
                    TranslationMemoryEntry.normalized_aliases.op("&&")(candidate_terms),
                ),
            )
            .order_by(
                TranslationMemoryEntry.scope_chapter.asc().nullsfirst(),
                TranslationMemoryEntry.updated_at.desc(),
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def fts_match(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        query_text: str,
        scope_chapter: int | None,
        limit: int,
    ) -> list[TranslationMemoryEntry]:
        if not query_text.strip():
            return []
        stmt = (
            select(TranslationMemoryEntry)
            .where(
                TranslationMemoryEntry.project_id == project_id,
                or_(
                    TranslationMemoryEntry.scope_chapter.is_(None),
                    TranslationMemoryEntry.scope_chapter == scope_chapter,
                ),
                TranslationMemoryEntry.search_document.op("@@")(
                    func.websearch_to_tsquery("simple", query_text)
                ),
            )
            .order_by(
                TranslationMemoryEntry.scope_chapter.asc().nullsfirst(),
                desc(
                    func.ts_rank_cd(
                        TranslationMemoryEntry.search_document,
                        func.websearch_to_tsquery("simple", query_text),
                    )
                ),
                TranslationMemoryEntry.updated_at.desc(),
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def vector_match(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        embedding_literal: str,
        scope_chapter: int | None,
        limit: int,
    ) -> list[TranslationMemoryEntry]:
        if not embedding_literal:
            return []
        query = text(
            """
            SELECT id
            FROM translation_memory_entries
            WHERE project_id = :project_id
              AND embedding IS NOT NULL
              AND (scope_chapter IS NULL OR scope_chapter = :scope_chapter)
            ORDER BY
              scope_chapter ASC NULLS FIRST,
              (embedding <=> CAST(:embedding_literal AS vector)) ASC,
              updated_at DESC
            LIMIT :limit
            """
        )
        rows = await db.execute(
            query,
            {
                "project_id": project_id,
                "scope_chapter": scope_chapter,
                "embedding_literal": embedding_literal,
                "limit": limit,
            },
        )
        ids = [row.id for row in rows]
        if not ids:
            return []

        stmt = select(TranslationMemoryEntry).where(TranslationMemoryEntry.id.in_(ids))
        result = await db.execute(stmt)
        by_id = {entry.id: entry for entry in result.scalars().all()}
        return [by_id[entry_id] for entry_id in ids if entry_id in by_id]

