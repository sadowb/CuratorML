from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_project_service
from app.schemas.chapter import ChapterCreateRequest, ChapterOut
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectEntryOut,
    ProjectListItem,
    ProjectWithChaptersOut,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects")

# TODO: Add pagination to list endpoints when we have more data. For now we can return all projects/chapters since we expect a small number of them.
# this is a post request and we are validating the payload using the ProjectCreateRequest schema. 
# We are also injecting the database session and the project service using FastAPI's dependency injection system. 
# The project service will handle the actual logic of creating a new project along with an initial chapter. 
# The response will be validated against the ProjectCreateResponse schema and we will return a 201 status code to indicate that a new resource has been created successfully.
@router.post("", response_model=ProjectCreateResponse, status_code=201)
async def create_project(
    payload: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectCreateResponse:
    return await project_service.create_project_with_initial_chapter(db, payload)


@router.get("", response_model=list[ProjectListItem])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> list[ProjectListItem]:
    return await project_service.list_projects_with_stats(db)


@router.get("/{project_id}", response_model=ProjectWithChaptersOut)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectWithChaptersOut:
    try:
        return await project_service.get_project_with_chapters(db, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/entry", response_model=ProjectEntryOut)
async def get_project_entry(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectEntryOut:
    try:
        return await project_service.get_project_entry(db, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/chapters", response_model=ChapterOut, status_code=201)
async def create_project_chapter(
    project_id: uuid.UUID,
    payload: ChapterCreateRequest,
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> ChapterOut:
    try:
        return await project_service.create_chapter(db, project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/chapters", response_model=list[ChapterOut])
async def list_project_chapters(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> list[ChapterOut]:
    try:
        return await project_service.list_project_chapters(db, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service),
) -> Response:
    try:
        await project_service.delete_project(db, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
