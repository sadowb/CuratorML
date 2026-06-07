from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_db, get_translation_memory_service
from app.schemas.memory import (
    EntryType,
    MemoryEntryBatchCreate,
    MemoryEntryBatchOut,
    MemoryEntryCreate,
    MemoryEntryOut,
    MemoryEntryUpdate,
)
from app.services.translation_memory_service import TranslationMemoryService

router = APIRouter(prefix="/projects/{project_id}/memory/entries", tags=["memory"])


@router.post("", response_model=MemoryEntryOut, status_code=status.HTTP_201_CREATED)
async def create_memory_entry(
    project_id: uuid.UUID,
    payload: MemoryEntryCreate,
    db: AsyncSession = Depends(get_db),
    memory_service: TranslationMemoryService = Depends(get_translation_memory_service),
) -> MemoryEntryOut:
    try:
        entry = await memory_service.create_entry(db, project_id=project_id, payload=payload)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="A memory entry with the same source term already exists for this scope",
        ) from exc
    return MemoryEntryOut.model_validate(entry)


@router.post("/batch", response_model=MemoryEntryBatchOut, status_code=status.HTTP_201_CREATED)
async def create_memory_entries_batch(
    project_id: uuid.UUID,
    payload: MemoryEntryBatchCreate,
    db: AsyncSession = Depends(get_db),
    memory_service: TranslationMemoryService = Depends(get_translation_memory_service),
) -> MemoryEntryBatchOut:
    created, failed = await memory_service.create_entries_batch(
        db,
        project_id=project_id,
        payloads=payload.entries,
    )
    return MemoryEntryBatchOut(
        created=[MemoryEntryOut.model_validate(entry) for entry in created],
        failed=failed,
    )


@router.get("", response_model=list[MemoryEntryOut])
async def list_memory_entries(
    project_id: uuid.UUID,
    entry_type: EntryType | None = Query(default=None),
    scope_chapter: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    memory_service: TranslationMemoryService = Depends(get_translation_memory_service),
) -> list[MemoryEntryOut]:
    entries = await memory_service.list_entries(
        db,
        project_id=project_id,
        entry_type=entry_type,
        scope_chapter=scope_chapter,
        q=q,
    )
    return [MemoryEntryOut.model_validate(entry) for entry in entries]


@router.patch("/{entry_id}", response_model=MemoryEntryOut)
async def update_memory_entry(
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: MemoryEntryUpdate,
    db: AsyncSession = Depends(get_db),
    memory_service: TranslationMemoryService = Depends(get_translation_memory_service),
) -> MemoryEntryOut:
    try:
        entry = await memory_service.update_entry(
            db,
            project_id=project_id,
            entry_id=entry_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="A memory entry with the same source term already exists for this scope",
        ) from exc
    return MemoryEntryOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_entry(
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    memory_service: TranslationMemoryService = Depends(get_translation_memory_service),
) -> Response:
    try:
        await memory_service.delete_entry(db, project_id=project_id, entry_id=entry_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
