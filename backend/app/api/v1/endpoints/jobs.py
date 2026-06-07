"""Job API endpoints — submit, poll, and SSE stream.

Endpoints
~~~~~~~~~
* ``POST /pages/{page_id}/jobs``  → submit a new pipeline job (202 Accepted)
* ``GET  /jobs/{job_id}``         → poll current status
* ``GET  /jobs/{job_id}/stream``  → SSE stream of real-time status changes
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.pipeline_run import PipelineRun
from app.schemas.job import JobSSEEvent, JobStatusResponse, JobSubmitRequest, JobSubmitResponse
from app.services.job_dispatcher import job_dispatcher
from app.services.job_event_bus import JobEvent, job_event_bus
from app.services.translation_errors import (
    TranslationDuplicateRunError,
    TranslationLanguageResolutionError,
)

logger = logging.getLogger("manga_api.jobs")

router = APIRouter(tags=["jobs"])


# ---------------------------------------------------------------------------
# POST /pages/{page_id}/jobs — Submit a pipeline job
# ---------------------------------------------------------------------------

@router.post(
    "/pages/{page_id}/jobs",
    response_model=JobSubmitResponse,
    status_code=202,
    summary="Submit a pipeline job",
    description="Accepts a pipeline stage to run for the given page. Returns"
    " immediately with the job id and a 202 status. Use the SSE"
    " stream or polling endpoint to track progress.",
)
async def submit_job(
    page_id: uuid.UUID,
    payload: JobSubmitRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> JobSubmitResponse:
    try:
        submit_kwargs = {}
        if payload.translate_options is not None:
            submit_kwargs["translate_options"] = payload.translate_options
        if payload.inpaint_options is not None:
            submit_kwargs["inpaint_options"] = payload.inpaint_options
        if payload.force:
            submit_kwargs["force"] = payload.force

        run = await job_dispatcher.submit(
            db,
            page_id,
            payload.stage,
            **submit_kwargs,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TranslationDuplicateRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TranslationLanguageResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.headers["Location"] = f"/api/v1/jobs/{run.id}"
    response.headers["Retry-After"] = "2"
    return JobSubmitResponse(
        job_id=run.id,
        page_id=run.page_id,
        stage=run.stage,
        status=run.status,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — Poll job status
# ---------------------------------------------------------------------------

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    run = await db.get(PipelineRun, job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=run.id,
        page_id=run.page_id,
        stage=run.stage,
        status=run.status,
        model_name=run.model_name,
        error_message=run.error_message,
        metrics_json=run.metrics_json,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/stream — SSE real-time status stream
# ---------------------------------------------------------------------------

_TERMINAL_STATUSES = frozenset({"completed", "failed"})


async def _sse_generator(job_id: str, queue: asyncio.Queue[JobEvent]):
    """Yield SSE-formatted events until the job reaches a terminal state."""
    try:
        while True:
            try:
                event: JobEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a keep-alive comment so proxies/browsers don't drop the connection.
                yield ": keepalive\n\n"
                continue

            sse_payload = JobSSEEvent(
                job_id=event.job_id,
                status=event.status,
                detail=event.detail,
                payload=event.payload,
            )
            yield f"event: job_update\ndata: {json.dumps(sse_payload.model_dump(mode='json'))}\n\n"

            if event.status in _TERMINAL_STATUSES:
                return
    except asyncio.CancelledError:
        return


@router.get(
    "/jobs/{job_id}/stream",
    summary="SSE stream of job status updates",
    description="Opens a Server-Sent Events stream. Receives events for"
    " status transitions (pending → running → completed/failed)."
    " The stream closes automatically when the job reaches a"
    " terminal state.",
)
async def stream_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Verify the job exists.
    run = await db.get(PipelineRun, job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job_id_str = str(job_id)

    # If already terminal, send one event and close.
    if run.status in _TERMINAL_STATUSES:
        async def _single_event():
            sse_payload = JobSSEEvent(
                job_id=job_id_str,
                status=run.status,
                detail=f"Job already {run.status}",
                payload=run.metrics_json,
            )
            yield f"event: job_update\ndata: {json.dumps(sse_payload.model_dump(mode='json'))}\n\n"

        return StreamingResponse(_single_event(), media_type="text/event-stream")

    queue = await job_event_bus.subscribe(job_id_str)

    async def _stream_with_cleanup():
        try:
            async for chunk in _sse_generator(job_id_str, queue):
                yield chunk
        finally:
            await job_event_bus.unsubscribe(job_id_str, queue)

    return StreamingResponse(
        _stream_with_cleanup(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
