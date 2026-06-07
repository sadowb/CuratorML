from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_image_export_service
from app.schemas.image_export import ImageExportRequest, ImageExportResponse
from app.services.image_export_service import ImageExportService


router = APIRouter(prefix="/pages")


@router.post("/{page_id}/exports/image", response_model=ImageExportResponse)
async def export_page_image(
    page_id: uuid.UUID,
    payload: ImageExportRequest,
    db: AsyncSession = Depends(get_db),
    image_export_service: ImageExportService = Depends(get_image_export_service),
) -> ImageExportResponse:
    try:
        file_kind, file_path, file_url = await image_export_service.export_page(
            db,
            page_id,
            format=payload.format,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    normalized_format = "jpg" if payload.format == "jpeg" else payload.format
    return ImageExportResponse(
        export_id=uuid.uuid4(),
        page_id=page_id,
        format=normalized_format,
        file_kind=file_kind,
        file_path=file_path,
        file_url=file_url,
    )
