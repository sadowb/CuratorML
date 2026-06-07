from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_storage_service
from app.services.storage_service import StorageService

router = APIRouter(prefix="/storage")


@router.get("/{project_id}/{chapter_id}/{page_id}/{file_kind}")
async def get_page_file(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    page_id: uuid.UUID,
    file_kind: str,
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> FileResponse:
    try:
        absolute_path, mime_type = await storage_service.resolve_page_file(
            db,
            project_id=project_id,
            chapter_id=chapter_id,
            page_id=page_id,
            file_kind=file_kind,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(path=absolute_path, media_type=mime_type)
