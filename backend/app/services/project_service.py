# this is the service layer for handling project related operations. 
# It interacts with the repositories to perform database operations and contains 
# the business logic for managing projects and their chapters.
from __future__ import annotations

from asyncio import log
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.project import Project
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.page_repository import PageRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.chapter import ChapterCreateRequest, ChapterOut
from app.schemas.project import ProjectCreateRequest
from app.schemas.project import (
    ProjectCreateResponse,
    ProjectEntryOut,
    ProjectListItem,
    ProjectOut,
    ProjectWithChaptersOut,
)
from app.services.response_mapper import map_project_list_items
from app.utils.storage import remove_project_storage


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository | None = None,
        chapter_repo: ChapterRepository | None = None,
        page_repo: PageRepository | None = None,
    ) -> None:
        self.project_repo = project_repo or ProjectRepository()
        self.chapter_repo = chapter_repo or ChapterRepository()
        self.page_repo = page_repo or PageRepository()

    async def create_project_with_initial_chapter(
        self,
        db: AsyncSession,
        payload: ProjectCreateRequest,
    ) -> ProjectCreateResponse:
        project = Project(
            name=payload.name,
            source_language=payload.source_language,
            target_language=payload.target_language,
            reading_direction=payload.reading_direction,
            context=payload.context,
            enable_ocr=payload.enable_ocr,
            require_qc=payload.require_qc,
            project_status="active",
        )

        project = await self.project_repo.create(db, project)

        chapter = Chapter(
            project_id=project.id,
            title=payload.chapter_title,
            chapter_number=payload.chapter_number,
            chapter_status="active",
        )
        chapter = await self.chapter_repo.create(db, chapter)

        return ProjectCreateResponse(project=ProjectOut.model_validate(project), chapter=ChapterOut.model_validate(chapter))

    async def list_projects_with_stats(self, db: AsyncSession) -> list[ProjectListItem]:
        rows = await self.project_repo.list_with_stats(db)
        return map_project_list_items(rows)

    async def get_project_with_chapters(self, db: AsyncSession, project_id: uuid.UUID) -> ProjectWithChaptersOut:
        project = await self.project_repo.get_by_id(db, project_id)
        if project is None:
            raise LookupError("Project not found")

        chapters = await self.chapter_repo.list_by_project(db, project_id)
        return ProjectWithChaptersOut(
            project=ProjectOut.model_validate(project),
            chapters=[ChapterOut.model_validate(chapter) for chapter in chapters],
        )

    async def get_project_entry(self, db: AsyncSession, project_id: uuid.UUID) -> ProjectEntryOut:
        project = await self.project_repo.get_by_id(db, project_id)
        if project is None:
            raise LookupError("Project not found")

        chapters = await self.chapter_repo.list_by_project(db, project_id)
        if not chapters:
            return ProjectEntryOut(
                project_id=project_id,
                chapter_id=None,
                page_id=None,
                editor_url=None,
                upload_url=f"/projects/{project_id}/upload",
                reason="chapter_required",
            )

        first_page = await self.page_repo.get_first_page_for_project(db, project_id)
        if first_page is not None:
            return ProjectEntryOut(
                project_id=project_id,
                chapter_id=first_page.chapter_id,
                page_id=first_page.id,
                editor_url=f"/editor/{project_id}/{first_page.id}",
                upload_url=f"/projects/{project_id}/upload?chapterId={first_page.chapter_id}",
                reason="editor_ready",
            )

        first_chapter = chapters[0]
        return ProjectEntryOut(
            project_id=project_id,
            chapter_id=first_chapter.id,
            page_id=None,
            editor_url=None,
            upload_url=f"/projects/{project_id}/upload?chapterId={first_chapter.id}",
            reason="upload_required",
        )

    async def create_chapter(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        payload: ChapterCreateRequest,
    ) -> ChapterOut:
        project = await self.project_repo.get_by_id(db, project_id)
        if project is None:
            raise LookupError("Project not found")

        chapter = await self.chapter_repo.create(
            db,
            chapter=Chapter(
                project_id=project_id,
                title=payload.title,
                chapter_number=payload.chapter_number,
                chapter_status="active",
            ),
        )
        return ChapterOut.model_validate(chapter)

    async def list_project_chapters(self, db: AsyncSession, project_id: uuid.UUID) -> list[ChapterOut]:
        project = await self.project_repo.get_by_id(db, project_id)
        if project is None:
            raise LookupError("Project not found")

        chapters = await self.chapter_repo.list_by_project(db, project_id)
        return [ChapterOut.model_validate(chapter) for chapter in chapters]

    async def delete_project(self, db: AsyncSession, project_id: uuid.UUID) -> None:
        log.logger.info(f"Deleting project {project_id}")
        deleted = await self.project_repo.delete_by_id(db, project_id)
        log.logger.info(f"Deleted project {project_id}: {deleted}")
        if not deleted:
            raise LookupError("Project not found")
        remove_project_storage(project_id)
