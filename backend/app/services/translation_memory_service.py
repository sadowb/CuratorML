from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.translation_memory_entry import TranslationMemoryEntry
from app.repositories.translation_memory_repository import TranslationMemoryRepository
from app.schemas.memory import (
    MemoryEntryBatchFailure,
    MemoryEntryCreate,
    MemoryEntryUpdate,
)

_KATAKANA = re.compile(r"[\u30A0-\u30FF]{2,}")
_JP_RUN = re.compile(r"[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF]{2,}")
_ROMAJI = re.compile(r"[A-Za-z][a-zA-Z\-\']{2,}")
_TSQUERY_TOKEN_SANITIZER = re.compile(r"[^0-9A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+")


def normalize_term(text: str) -> str:
    value = unicodedata.normalize("NFKC", (text or "").strip())
    value = re.sub(r"ー+", "", value)
    return value.lower()


def extract_term_candidates(ocr_lines: list[str]) -> list[str]:
    candidates: set[str] = set()
    for line in ocr_lines:
        candidates.update(_KATAKANA.findall(line))
        candidates.update(_JP_RUN.findall(line))
        candidates.update(_ROMAJI.findall(line))

    normalized = {normalize_term(item) for item in candidates if item}
    return [item for item in normalized if len(item) >= 2]


def _sanitize_fts_query_text(text_value: str) -> str:
    tokens = [
        _TSQUERY_TOKEN_SANITIZER.sub("", token).strip()
        for token in text_value.split()
    ]
    clean_tokens = [token for token in tokens if token]
    return " ".join(clean_tokens)


class TranslationMemoryService:
    def __init__(
        self,
        repo: TranslationMemoryRepository | None = None,
    ) -> None:
        self.repo = repo or TranslationMemoryRepository()
        api_key = (
            settings.translation_memory_embedding_api_key.get_secret_value()
            if settings.translation_memory_embedding_api_key
            else "not-needed"
        )
        self._embed_client = AsyncOpenAI(
            base_url=settings.translation_memory_embedding_base_url,
            api_key=api_key,
            timeout=30.0,
            max_retries=0,
        )

    async def create_entry(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        payload: MemoryEntryCreate,
    ) -> TranslationMemoryEntry:
        normalized_source = normalize_term(payload.source_term)
        normalized_aliases = sorted({normalize_term(alias) for alias in payload.aliases if alias})
        embedding = await self._build_entry_embedding(
            source_term=payload.source_term,
            aliases=payload.aliases,
            notes=payload.notes,
        )
        entry = TranslationMemoryEntry(
            project_id=project_id,
            entry_type=payload.entry_type,
            source_term=payload.source_term.strip(),
            preferred_translation=payload.preferred_translation.strip(),
            scope_chapter=payload.scope_chapter,
            aliases=payload.aliases,
            notes=(payload.notes or "").strip() or None,
            normalized_source_term=normalized_source,
            normalized_aliases=normalized_aliases,
            embedding=embedding,
        )
        return await self.repo.create(db, entry)

    async def create_entries_batch(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        payloads: list[MemoryEntryCreate],
    ) -> tuple[list[TranslationMemoryEntry], list[MemoryEntryBatchFailure]]:
        created: list[TranslationMemoryEntry] = []
        failed: list[MemoryEntryBatchFailure] = []

        for index, payload in enumerate(payloads):
            try:
                async with db.begin_nested():
                    entry = await self.create_entry(
                        db,
                        project_id=project_id,
                        payload=payload,
                    )
                    created.append(entry)
            except Exception as exc:  # noqa: BLE001
                failed.append(
                    MemoryEntryBatchFailure(
                        index=index,
                        source_term=payload.source_term,
                        detail=str(exc),
                    )
                )
        return created, failed

    async def list_entries(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        entry_type: str | None = None,
        scope_chapter: int | None = None,
        q: str | None = None,
    ) -> list[TranslationMemoryEntry]:
        return await self.repo.list_for_project(
            db,
            project_id=project_id,
            entry_type=entry_type,
            scope_chapter=scope_chapter,
            q=q,
        )

    async def update_entry(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        entry_id: uuid.UUID,
        payload: MemoryEntryUpdate,
    ) -> TranslationMemoryEntry:
        entry = await self.repo.get_by_id(db, project_id=project_id, entry_id=entry_id)
        if entry is None:
            raise LookupError("Memory entry not found")

        changed_embedding_fields = False
        if payload.entry_type is not None:
            entry.entry_type = payload.entry_type
        if payload.source_term is not None:
            entry.source_term = payload.source_term.strip()
            entry.normalized_source_term = normalize_term(entry.source_term)
            changed_embedding_fields = True
        if payload.preferred_translation is not None:
            entry.preferred_translation = payload.preferred_translation.strip()
        if payload.scope_chapter is not None:
            entry.scope_chapter = payload.scope_chapter
        if payload.aliases is not None:
            entry.aliases = payload.aliases
            entry.normalized_aliases = sorted(
                {normalize_term(alias) for alias in payload.aliases if alias}
            )
            changed_embedding_fields = True
        if payload.notes is not None:
            entry.notes = payload.notes.strip() or None
            changed_embedding_fields = True

        if changed_embedding_fields:
            entry.embedding = await self._build_entry_embedding(
                source_term=entry.source_term,
                aliases=entry.aliases,
                notes=entry.notes,
            )

        await db.flush()
        await db.refresh(entry)
        return entry

    async def delete_entry(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> None:
        entry = await self.repo.get_by_id(db, project_id=project_id, entry_id=entry_id)
        if entry is None:
            raise LookupError("Memory entry not found")
        await self.repo.delete(db, entry)

    async def retrieve_for_page(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        scope_chapter: int | None,
        ocr_lines: list[str],
        story_context: str | None,
    ) -> dict[str, Any]:
        candidates = extract_term_candidates(ocr_lines)

        exact_rows = await self.repo.exact_match(
            db,
            project_id=project_id,
            candidate_terms=candidates,
            scope_chapter=scope_chapter,
            limit=settings.translation_memory_top_k_exact,
        )

        seen_terms = {row.normalized_source_term for row in exact_rows}
        filtered_candidates = [item for item in candidates if item not in seen_terms]

        fts_rows = await self.repo.fts_match(
            db,
            project_id=project_id,
            query_text=_sanitize_fts_query_text(
                " ".join(filtered_candidates + ocr_lines + [story_context or ""])
            ),
            scope_chapter=scope_chapter,
            limit=settings.translation_memory_top_k_fts,
        )

        seen_ids = {row.id for row in exact_rows + fts_rows}
        vector_rows: list[TranslationMemoryEntry] = []
        if not exact_rows and not fts_rows:
            query_embedding = await self._embed_query_text(story_context or " ".join(ocr_lines))
            if query_embedding:
                vector_rows = await self.repo.vector_match(
                    db,
                    project_id=project_id,
                    embedding_literal=self._to_vector_literal(query_embedding),
                    scope_chapter=scope_chapter,
                    limit=settings.translation_memory_top_k_vector,
                )

        merged = self._rank_and_deduplicate(
            exact_rows=exact_rows,
            fts_rows=fts_rows,
            vector_rows=vector_rows,
        )
        merged = [item for item in merged if item.id not in seen_ids or item in exact_rows + fts_rows]

        hard_rules: list[dict[str, Any]] = []
        soft_notes: list[dict[str, Any]] = []

        for entry in merged:
            payload = {
                "entry_type": entry.entry_type,
                "source_term": entry.source_term,
                "preferred_translation": entry.preferred_translation,
                "aliases": entry.aliases,
                "notes": entry.notes,
                "scope_chapter": entry.scope_chapter,
            }
            if entry.scope_chapter is None:
                hard_rules.append(payload)
            else:
                soft_notes.append(payload)

        return {
            "hard_glossary_rules": hard_rules[: settings.translation_memory_max_hard_rules],
            "soft_notes": soft_notes[: settings.translation_memory_max_soft_notes],
            "stats": {
                "candidate_count": len(candidates),
                "exact_count": len(exact_rows),
                "fts_count": len(fts_rows),
                "vector_count": len(vector_rows),
                "hard_count": len(hard_rules),
                "soft_count": len(soft_notes),
            },
        }

    def _rank_and_deduplicate(
        self,
        *,
        exact_rows: list[TranslationMemoryEntry],
        fts_rows: list[TranslationMemoryEntry],
        vector_rows: list[TranslationMemoryEntry],
    ) -> list[TranslationMemoryEntry]:
        ranked: list[tuple[int, TranslationMemoryEntry]] = []
        for row in exact_rows:
            ranked.append((0, row))
        for row in fts_rows:
            ranked.append((1, row))
        for row in vector_rows:
            ranked.append((2, row))

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1].scope_chapter is not None,  # project scope first
                -item[1].updated_at.timestamp(),
            )
        )
        dedup: dict[str, TranslationMemoryEntry] = {}
        for _, row in ranked:
            key = row.normalized_source_term
            if key not in dedup:
                dedup[key] = row
        return list(dedup.values())

    async def _build_entry_embedding(
        self,
        *,
        source_term: str,
        aliases: list[str],
        notes: str | None,
    ) -> list[float] | None:
        text_value = " ".join(
            item for item in [source_term, " ".join(aliases), notes or ""] if item
        ).strip()
        if not text_value:
            return None
        return await self._embed_query_text(text_value)

    async def _embed_query_text(self, text_value: str) -> list[float] | None:
        if not text_value.strip():
            return None
        try:
            response = await self._embed_client.embeddings.create(
                model=settings.translation_memory_embedding_model,
                input=text_value,
            )
        except Exception:
            return None

        if not response.data:
            return None
        vector = list(response.data[0].embedding)
        expected_dim = settings.translation_memory_embedding_dimensions
        if expected_dim and len(vector) != expected_dim:
            return None
        return vector

    @staticmethod
    def _to_vector_literal(vector: list[float]) -> str:
        joined = ",".join(str(float(v)) for v in vector)
        return f"[{joined}]"
