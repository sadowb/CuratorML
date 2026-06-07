from __future__ import annotations

import uuid
from pathlib import PurePosixPath


def normalized_page_file_path(
    current_path: str,
    *,
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    page_id: uuid.UUID,
) -> str:
    filename = PurePosixPath(current_path).name
    if not filename:
        raise ValueError("file_path has no filename")
    return str(
        PurePosixPath(
            f"project_{project_id}",
            f"chapter_{chapter_id}",
            f"page_{page_id}",
            filename,
        )
    )


def needs_page_file_path_migration(
    current_path: str,
    *,
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    page_id: uuid.UUID,
) -> bool:
    return current_path != normalized_page_file_path(
        current_path,
        project_id=project_id,
        chapter_id=chapter_id,
        page_id=page_id,
    )
