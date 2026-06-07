from __future__ import annotations

import uuid

from app.utils.page_file_path_migration import (
    needs_page_file_path_migration,
    normalized_page_file_path,
)


def test_normalized_page_file_path_uses_page_uuid_segment() -> None:
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    current = f"project_{project_id}/chapter_{chapter_id}/page_5/original.jpg"

    normalized = normalized_page_file_path(
        current,
        project_id=project_id,
        chapter_id=chapter_id,
        page_id=page_id,
    )
    assert normalized == f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/original.jpg"


def test_needs_migration_when_using_old_page_number_segment() -> None:
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    current = f"project_{project_id}/chapter_{chapter_id}/page_12/original.webp"

    assert needs_page_file_path_migration(
        current,
        project_id=project_id,
        chapter_id=chapter_id,
        page_id=page_id,
    )


def test_no_migration_needed_when_already_normalized() -> None:
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    current = f"project_{project_id}/chapter_{chapter_id}/page_{page_id}/original.png"

    assert not needs_page_file_path_migration(
        current,
        project_id=project_id,
        chapter_id=chapter_id,
        page_id=page_id,
    )
