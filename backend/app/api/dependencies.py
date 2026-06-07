from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.chapter_service import ChapterService
from app.services.image_export_service import ImageExportService
from app.services.page_service import PageService
from app.services.psd_export.service import PsdExportService
from app.services.project_service import ProjectService
from app.services.storage_service import StorageService
from app.services.translation_memory_service import TranslationMemoryService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_project_service() -> ProjectService:
    return ProjectService()


def get_chapter_service() -> ChapterService:
    return ChapterService()


def get_page_service() -> PageService:
    return PageService()


def get_psd_export_service() -> PsdExportService:
    return PsdExportService()


def get_image_export_service() -> ImageExportService:
    return ImageExportService()


def get_storage_service() -> StorageService:
    return StorageService()


def get_translation_memory_service() -> TranslationMemoryService:
    return TranslationMemoryService()
