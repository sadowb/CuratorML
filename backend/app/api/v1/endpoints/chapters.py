from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chapter_service, get_db
from app.schemas.page import PaginatedPageSummaryOut, PageUploadResponse
from app.services.chapter_service import ChapterService

router = APIRouter(prefix="/chapters")


@router.post("/{chapter_id}/pages/upload", response_model=PageUploadResponse, status_code=201)
async def upload_chapter_pages(
    chapter_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    chapter_service: ChapterService = Depends(get_chapter_service),
) -> PageUploadResponse:
    try:
        return await chapter_service.upload_pages(db, chapter_id, files)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{chapter_id}/pages", response_model=PaginatedPageSummaryOut)
async def list_chapter_pages(
    chapter_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    chapter_service: ChapterService = Depends(get_chapter_service),
) -> PaginatedPageSummaryOut:
    try:
        return await chapter_service.list_pages(
            db,
            chapter_id,
            page=page,
            page_size=page_size,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
