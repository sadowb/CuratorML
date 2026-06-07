from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.storage_repository import StorageRepository
from app.utils.storage import resolve_storage_path


class StorageService:
    def __init__(self, storage_repo: StorageRepository | None = None) -> None:
        self.storage_repo = storage_repo or StorageRepository()

    async def resolve_page_file(
        self,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID,
        page_id: uuid.UUID,
        file_kind: str,
    ) -> tuple[Path, str]:
        page_file = await self.storage_repo.get_file_for_storage_path(
            db=db,
            project_id=project_id,
            chapter_id=chapter_id,
            page_id=page_id,
            file_kind=file_kind,
        )
        if page_file is None:
            raise LookupError("File not found")

        try:
            absolute_path = resolve_storage_path(page_file.file_path)
        except ValueError as exc:
            raise ValueError("Invalid file path") from exc

        if not absolute_path.exists() or not absolute_path.is_file():
            raise LookupError("File missing on disk")

        return absolute_path, page_file.mime_type
