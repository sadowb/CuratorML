from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.models.translation_memory_entry import TranslationMemoryEntry
from app.services.translation_memory_service import TranslationMemoryService


def _entry(
    *,
    source_term: str,
    preferred_translation: str,
    scope_chapter: int | None = None,
    normalized_source_term: str | None = None,
) -> TranslationMemoryEntry:
    now = datetime.now(timezone.utc)
    return TranslationMemoryEntry(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        entry_type="character",
        source_term=source_term,
        preferred_translation=preferred_translation,
        scope_chapter=scope_chapter,
        aliases=[],
        notes=None,
        normalized_source_term=normalized_source_term or source_term.lower(),
        normalized_aliases=[],
        embedding=None,
        search_document=None,
        created_at=now,
        updated_at=now,
    )


async def test_retrieve_exact_then_fts_without_vector_when_hits_exist() -> None:
    repo = AsyncMock()
    service = TranslationMemoryService(repo=repo)
    service._embed_query_text = AsyncMock(return_value=[0.1] * 1024)  # type: ignore[attr-defined]

    exact_rows = [_entry(source_term="ゾロ", preferred_translation="Zoro")]
    fts_rows = [_entry(source_term="海軍", preferred_translation="Marines")]

    repo.exact_match.return_value = exact_rows
    repo.fts_match.return_value = fts_rows
    repo.vector_match.return_value = []

    block = await service.retrieve_for_page(
        db=object(),  # type: ignore[arg-type]
        project_id=uuid.uuid4(),
        scope_chapter=1,
        ocr_lines=["ゾロ", "海軍"],
        story_context="",
    )

    assert block["hard_glossary_rules"]
    assert block["stats"]["exact_count"] == 1
    assert block["stats"]["fts_count"] == 1
    repo.vector_match.assert_not_called()


async def test_retrieve_uses_vector_fallback_only_when_exact_and_fts_empty() -> None:
    repo = AsyncMock()
    service = TranslationMemoryService(repo=repo)
    service._embed_query_text = AsyncMock(return_value=[0.2] * 1024)  # type: ignore[attr-defined]

    vector_rows = [_entry(source_term="鬼斬り", preferred_translation="Oni Giri")]
    repo.exact_match.return_value = []
    repo.fts_match.return_value = []
    repo.vector_match.return_value = vector_rows

    block = await service.retrieve_for_page(
        db=object(),  # type: ignore[arg-type]
        project_id=uuid.uuid4(),
        scope_chapter=1,
        ocr_lines=["鬼斬り"],
        story_context="",
    )

    assert block["stats"]["vector_count"] == 1
    assert block["hard_glossary_rules"] or block["soft_notes"]
    repo.vector_match.assert_called_once()


def test_rank_prefers_project_scope_over_chapter_for_same_term() -> None:
    service = TranslationMemoryService(repo=AsyncMock())
    project_entry = _entry(
        source_term="ゾロ",
        preferred_translation="Zoro",
        scope_chapter=None,
        normalized_source_term="ゾロ",
    )
    chapter_entry = _entry(
        source_term="ゾロ",
        preferred_translation="Zolo",
        scope_chapter=2,
        normalized_source_term="ゾロ",
    )

    ranked = service._rank_and_deduplicate(  # pylint: disable=protected-access
        exact_rows=[chapter_entry, project_entry],
        fts_rows=[],
        vector_rows=[],
    )
    assert len(ranked) == 1
    assert ranked[0].preferred_translation == "Zoro"
