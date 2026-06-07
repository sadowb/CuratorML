from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_psd_export_service
from app.schemas.psd_export import PsdExportRequest, PsdExportResponse, PsdExportCanvasOut, PsdExportOutputsOut
from app.services.psd_export.service import PsdExportService


router = APIRouter(prefix="/pages")


@router.post("/{page_id}/exports/psd", response_model=PsdExportResponse)
async def export_page_psd(
    page_id: uuid.UUID,
    payload: PsdExportRequest,
    db: AsyncSession = Depends(get_db),
    psd_export_service: PsdExportService = Depends(get_psd_export_service),
) -> PsdExportResponse:
    """Export one page as layered PSD + manifest JSON."""
    try:
        result = await psd_export_service.export_page(
            db,
            page_id,
            include_preview=payload.include_preview,
            include_ocr_notes=payload.include_ocr_notes,
            include_brush_cleanup=payload.include_brush_cleanup,
            include_merged_preview=payload.include_merged_preview,
            original_visible=payload.original_visible,
            inpainted_visible=payload.inpainted_visible,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PsdExportResponse(
        export_id=result.export_id,
        page_id=result.page_id,
        writer=result.writer,
        writer_version=result.writer_version,
        canvas=PsdExportCanvasOut(width=result.canvas.width, height=result.canvas.height),
        outputs=PsdExportOutputsOut(
            psd_path=result.psd_path,
            manifest_path=result.manifest_path,
            psd_url=result.psd_url,
            manifest_url=result.manifest_url,
        ),
        layer_count=result.layer_count,
        manifest=result.manifest,
    )
