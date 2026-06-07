from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_page_service
from app.schemas.page import (
    PageDetailOut,
    PageInpaintCleanupOut,
    PageInpaintCleanupRequest,
    PageInpaintResultOut,
    PageOcrResultOut,
    PageReadingOrderOut,
    PageTextsReadOut,
    PageTextOut,
    PageTextPatchRequest,
)
from app.schemas.mask_inference import MaskInferenceResponse
from app.schemas.page_region import PageRegionOut, PageRegionPatchRequest, PageRegionCreateRequest
from app.services.page_service import PageService


router = APIRouter(prefix="/pages")


@router.get("/{page_id}", response_model=PageDetailOut)
async def get_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageDetailOut:
    try:
        return await page_service.get_page_detail(db, page_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{page_id}/ocr", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def submit_ocr(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raise HTTPException(
        status_code=405,
        detail='Use POST /api/v1/pages/{page_id}/jobs with {"stage":"ocr"}',
    )


@router.get("/{page_id}/ocr", response_model=PageOcrResultOut)
async def get_ocr_result(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageOcrResultOut:
    try:
        return await page_service.get_page_ocr_result(db, page_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{page_id}/texts", response_model=PageTextsReadOut)
async def get_page_texts(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageTextsReadOut:
    try:
        return await page_service.get_page_texts(db, page_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{page_id}/reading-order", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def submit_reading_order(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raise HTTPException(
        status_code=405,
        detail='Use POST /api/v1/pages/{page_id}/jobs with {"stage":"reading_order"}',
    )


@router.get("/{page_id}/reading-order", response_model=PageReadingOrderOut)
async def get_reading_order(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageReadingOrderOut:
    try:
        return await page_service.get_page_reading_order(db, page_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{page_id}/inpaint", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def submit_inpaint(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raise HTTPException(
        status_code=405,
        detail='Use POST /api/v1/pages/{page_id}/jobs with {"stage":"inpaint"}',
    )


@router.get("/{page_id}/inpaint", response_model=PageInpaintResultOut)
async def get_inpaint_result(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageInpaintResultOut:
    try:
        return await page_service.get_page_inpaint_result(db, page_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{page_id}/inpaint/cleanup", response_model=PageInpaintCleanupOut)
async def save_inpaint_cleanup(
    page_id: uuid.UUID,
    payload: PageInpaintCleanupRequest,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageInpaintCleanupOut:
    try:
        return await page_service.save_inpaint_cleanup(db, page_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{page_id}/texts/{text_id}", response_model=PageTextOut)
async def patch_page_text(
    page_id: uuid.UUID,
    text_id: uuid.UUID,
    payload: PageTextPatchRequest,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageTextOut:
    try:
        return await page_service.patch_page_text(db, page_id, text_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{page_id}/regions", response_model=PageRegionOut, status_code=status.HTTP_201_CREATED)
async def create_page_region(
    page_id: uuid.UUID,
    payload: PageRegionCreateRequest,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageRegionOut:
    try:
        return await page_service.create_page_region(db, page_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{page_id}/regions/{region_id}", response_model=PageRegionOut)
async def patch_page_region(
    page_id: uuid.UUID,
    region_id: uuid.UUID,
    payload: PageRegionPatchRequest,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> PageRegionOut:
    try:
        return await page_service.patch_page_region(db, page_id, region_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{page_id}/mask-inference", response_model=MaskInferenceResponse)
async def run_mask_inference(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page_service: PageService = Depends(get_page_service),
) -> MaskInferenceResponse:
    """Legacy synchronous mask-inference endpoint.

    Kept for backward compatibility. Prefer ``POST /pages/{page_id}/jobs``
    with ``stage="mask_inference"`` for async execution.
    """
    try:
        return await page_service.run_mask_inference(db, page_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
