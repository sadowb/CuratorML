"""Async job dispatcher — runs ML pipeline stages off the event loop.

Supports two execution modes controlled by ``settings.inference_mode``:

* **local** — wraps the blocking ML call in ``asyncio.to_thread()`` so the
  FastAPI event loop stays free.  YOLO segmentation and OCR work run in the
  default ``ThreadPoolExecutor``; inpainting cleanup is traditional mask/OpenCV
  processing, not a learned model.
* **remote** — forwards the request to an external inference server via
  ``httpx`` (e.g. a GPU box, Google Colab, cloud VM).

Both modes follow the same lifecycle:
  1. Create a ``PipelineRun`` row (status ``pending``)  → return job_id.
  2. Fire a background ``asyncio.Task`` that:
     a) sets status → ``running``
     b) executes the stage handler
     c) persists results (regions, files, …)
     d) sets status → ``completed`` | ``failed``
  3. After each status transition, publish a ``JobEvent`` so any SSE
     subscriber gets a real-time update.

Design notes
~~~~~~~~~~~~
* **No Celery / Redis** — a single asyncio task is the right primitive for a
  sequential one-page-at-a-time workflow on 8 GB RAM.
* **Generic stage router** — ``_STAGE_HANDLERS`` maps stage names to handler
  coroutines.  Adding inpainting or reading-order estimation later is just
  registering a new handler.
* **Structured cancellation** — tasks are tracked so the lifespan shutdown
  can await them cleanly.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import langcodes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.models.chapter import Chapter
from app.models.page import Page
from app.models.page_region import PageRegion
from app.models.pipeline_run import PipelineRun
from app.models.project import Project
from app.schemas.job import InpaintOptions
from app.schemas.translation import TranslateOptions
from app.services.job_event_bus import JobEvent, job_event_bus
from app.services.inpaint_page_service import InpaintPageService
from app.services.ocr_service import OcrService
from app.services.page_helper_image_service import PageHelperImageService
from app.services.reading_order_estimation_service import ReadingOrderEstimationService
from app.services.translation_errors import (
    TranslationDuplicateRunError,
    TranslationLanguageResolutionError,
)
from app.services.translation_service import TranslationService
from app.utils.storage import resolve_storage_path

logger = logging.getLogger("manga_api.job_dispatcher")

ocr_service = OcrService()
reading_order_service = ReadingOrderEstimationService()
inpaint_page_service = InpaintPageService()
translation_service = TranslationService()
page_helper_image_service = PageHelperImageService()


# ---------------------------------------------------------------------------
# Stage handler type
# ---------------------------------------------------------------------------

# Each handler receives (db_session, pipeline_run, page) and returns a dict
# of optional metadata that gets merged into ``PipelineRun.metrics_json``.
StageHandler = Any  # Callable[..., Coroutine]  (simplified for 3.12 compat)


# ---------------------------------------------------------------------------
# Mask inference handler
# ---------------------------------------------------------------------------

async def _handle_mask_inference(
    db: AsyncSession,
    run: PipelineRun,
    page: Page,
) -> dict[str, Any]:
    """Run YOLO mask inference in a background thread and persist results."""

    # Resolve the source image from the page's current files.
    image_file = next(
        (f for f in page.files if f.file_kind == "original" and f.is_current),
        page.files[0] if page.files else None,
    )
    if image_file is None:
        raise ValueError("No image file associated with this page")

    resolved_path = resolve_storage_path(image_file.file_path)
    if not resolved_path.exists():
        raise ValueError(f"Source image not found: {resolved_path}")

    # CPU/GPU-bound — run off the event loop.
    if settings.inference_mode == "local":
        from app.services.ml.yolo_inference_service import run_inference
        detections = await asyncio.to_thread(
            run_inference, str(resolved_path),
        )
    else:
        detections = await _call_remote_inference(str(resolved_path), "mask_inference")

    # Deactivate previous mask-inference regions for this page.
    for region in page.regions:
        if region.is_active and region.origin == "mask_inference":
            region.is_active = False

    # Persist new regions.
    for detection in detections:
        db.add(
            PageRegion(
                page_id=page.id,
                pipeline_run_id=run.id,
                created_by_user_id=None,
                region_kind=detection["region_kind"],
                polygon_json=detection["mask"],
                bbox_json=detection["box"],
                confidence=detection["conf"],
                reading_order=None,
                origin="mask_inference",
                is_active=True,
            )
        )

    return {"detection_count": len(detections)}


async def _handle_ocr(
    db: AsyncSession,
    run: PipelineRun,
    page: Page,
) -> dict[str, Any]:
    reading_order_metrics = await reading_order_service.run_for_page(
        db,
        page=page,
        pipeline_run_id=run.id,
    )
    ocr_metrics = await ocr_service.run_for_page(
        db,
        page=page,
        pipeline_run_id=run.id,
    )
    return {
        "reading_order": reading_order_metrics,
        "ocr": ocr_metrics,
    }


async def _handle_reading_order(
    db: AsyncSession,
    run: PipelineRun,
    page: Page,
) -> dict[str, Any]:
    return await reading_order_service.run_for_page(db, page=page, pipeline_run_id=run.id)


async def _handle_inpaint(
    db: AsyncSession,
    run: PipelineRun,
    page: Page,
) -> dict[str, Any]:
    params = run.input_params_json or {}
    options = InpaintOptions.model_validate(params.get("inpaint_options", {}))
    return await inpaint_page_service.run_for_page(
        db,
        page=page,
        pipeline_run_id=run.id,
        options=options,
    )


async def _handle_helper_grounded(
    db: AsyncSession,
    run: PipelineRun,
    page: Page,
) -> dict[str, Any]:
    result = await page_helper_image_service.generate_grounded_helper(
        db,
        page=page,
        pipeline_run_id=run.id,
        persist_debug=True,
    )
    return {
        "marker_count": result.marker_count,
        "skipped_regions": result.skipped_regions,
        "source_file_kind": result.source_file_kind,
        "helper_grounded_path": result.persisted_artifact_path,
    }


# ---------------------------------------------------------------------------
# Remote inference helper (httpx)
# ---------------------------------------------------------------------------

async def _call_remote_inference(
    image_path: str,
    stage: str,
) -> list[dict[str, Any]]:
    """POST image to a remote inference API and convert the response.

    The Docker backend must not import the local YOLO implementation here.
    Heavy ML dependencies such as scipy/ultralytics live in the host inference
    service, so remote mode returns plain detection dictionaries.
    """
    import httpx

    timeout = httpx.Timeout(settings.inference_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        with open(image_path, "rb") as f:
            resp = await client.post(
                f"{settings.inference_remote_url}/infer/{stage}",
                files={"image": (image_path.split("/")[-1], f, "image/png")},
            )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "id": d["id"],
                "region_kind": d["region_kind"],
                "box": d["box"],
                "conf": d["conf"],
                "mask": d["mask"],
            }
            for d in data.get("detections", [])
        ]


async def _handle_translate(
    db: AsyncSession,
    run: PipelineRun,
    page: Page,
) -> dict[str, Any]:
    """Translate text regions using the LLM gateway.

    Reads all configuration from ``run.input_params_json`` which was
    resolved and persisted at submit time.
    """
    params = run.input_params_json or {}
    options = TranslateOptions.model_validate(params.get("translate_options", {}))
    effective_language = params.get("effective_target_language", "")
    if not effective_language:
        raise ValueError("effective_target_language missing from input_params_json")

    return await translation_service.run_for_page(
        db,
        page=page,
        pipeline_run_id=run.id,
        options=options,
        effective_target_language=effective_language,
    )


# ---------------------------------------------------------------------------
# Stage handler registry
# ---------------------------------------------------------------------------

_STAGE_HANDLERS: dict[str, StageHandler] = {
    "mask_inference": _handle_mask_inference,
    "ocr": _handle_ocr,
    "inpaint": _handle_inpaint,
    "helper_grounded": _handle_helper_grounded,
    "reading_order": _handle_reading_order,
    "translate": _handle_translate,
}


# ---------------------------------------------------------------------------
# Job dispatcher
# ---------------------------------------------------------------------------

class JobDispatcher:
    """Accepts pipeline jobs and runs them asynchronously."""

    def __init__(self) -> None:
        self._running_tasks: set[asyncio.Task[None]] = set()

    # -- public API ---------------------------------------------------------

    async def submit(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        stage: str,
        *,
        translate_options: TranslateOptions | None = None,
        inpaint_options: InpaintOptions | None = None,
        force: bool = False,
    ) -> PipelineRun:
        """Create a pending ``PipelineRun`` and schedule execution.

        Returns immediately so the API can respond with 202.
        """
        if stage not in _STAGE_HANDLERS:
            raise ValueError(f"Unknown pipeline stage: {stage}")

        # Validate that the page exists and eager-load relationships we need.
        load_options = [
            selectinload(Page.files),
            selectinload(Page.regions).selectinload(PageRegion.texts),
        ]
        # Translation needs project for language fallback.
        if stage == "translate":
            load_options.append(
                selectinload(Page.chapter).selectinload(Chapter.project)
            )
        else:
            load_options.append(selectinload(Page.chapter))

        stmt = (
            select(Page)
            .options(*load_options)
            .where(Page.id == page_id)
        )
        result = await db.execute(stmt)
        page = result.scalar_one_or_none()
        if page is None:
            raise LookupError("Page not found")

        # ── Translation submit-time resolution (Packet 4) ─────────
        input_params: dict[str, Any] | None = None
        if stage == "translate" and translate_options is not None:
            effective_language = _resolve_target_language(
                translate_options, page,
            )

            # Auto-inject project context if available and not explicitly provided in options.
            project = page.chapter.project if page.chapter else None
            if project and hasattr(project, "context") and project.context and not translate_options.story_context:
                translate_options.story_context = project.context

            # Duplicate active run check (simple safety net).
            await _check_duplicate_translate_run(
                db, page_id, effective_language, force=force
            )
            safe_translate_options = translate_options.model_dump(
                mode="json",
                exclude={"provider_override": {"api_key"}},
            )
            input_params = {
                "translate_options": safe_translate_options,
                "effective_target_language": effective_language,
            }
        elif stage == "inpaint" and inpaint_options is not None:
            input_params = {
                "inpaint_options": inpaint_options.model_dump(mode="json"),
            }

        # Create the job record.
        run = PipelineRun(
            page_id=page.id,
            stage=stage,
            model_name="yolo" if stage == "mask_inference" else None,
            status="pending",
            input_params_json=input_params,
            started_at=None,
            finished_at=None,
        )
        db.add(run)
        await db.flush()  # Assigns run.id
        await db.commit()

        job_id = str(run.id)

        # Publish initial event.
        await job_event_bus.publish(JobEvent(
            job_id=job_id,
            status="pending",
            detail=f"Job {stage} queued",
        ))

        # Fire background task — uses its own DB session.
        task = asyncio.create_task(
            self._execute(job_id, page_id, stage),
            name=f"job-{job_id}",
        )
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)

        return run

    async def shutdown(self) -> None:
        """Cancel and await all running tasks (called from lifespan)."""
        for task in self._running_tasks:
            task.cancel()
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()

    # -- internal -----------------------------------------------------------

    async def _execute(
        self,
        job_id: str,
        page_id: uuid.UUID,
        stage: str,
    ) -> None:
        """Run the pipeline stage in its own DB session."""
        handler = _STAGE_HANDLERS[stage]

        async with AsyncSessionFactory() as db:
            # Re-fetch objects in this session.
            run = await db.get(PipelineRun, uuid.UUID(job_id))
            if run is None:
                logger.error("PipelineRun %s disappeared before execution", job_id)
                return

            stmt = (
                select(Page)
                .options(
                    selectinload(Page.files),
                    selectinload(Page.chapter),
                    selectinload(Page.regions).selectinload(PageRegion.texts),
                )
                .where(Page.id == page_id)
            )
            result = await db.execute(stmt)
            page = result.scalar_one_or_none()
            if page is None:
                run.status = "failed"
                run.error_message = "Page not found"
                await db.commit()
                await job_event_bus.publish(JobEvent(
                    job_id=job_id, status="failed", detail="Page not found",
                ))
                return

            # Mark running.
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()
            await job_event_bus.publish(JobEvent(
                job_id=job_id, status="running", detail=f"Executing {stage}",
            ))

            try:
                metrics = await handler(db, run, page)
                run.status = "completed"
                run.finished_at = datetime.now(timezone.utc)
                run.metrics_json = metrics or {}
                await db.commit()

                await job_event_bus.publish(JobEvent(
                    job_id=job_id,
                    status="completed",
                    detail=f"{stage} finished",
                    payload=metrics,
                ))
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                run.status = "failed"
                run.finished_at = datetime.now(timezone.utc)
                run.error_message = str(exc)[:500]
                await db.commit()

                await job_event_bus.publish(JobEvent(
                    job_id=job_id,
                    status="failed",
                    detail=str(exc)[:200],
                ))


# ---------------------------------------------------------------------------
# Translation submit-time helpers (Packet 4)
# ---------------------------------------------------------------------------


def _resolve_target_language(
    options: TranslateOptions,
    page: Page,
) -> str:
    """Resolve effective target language: request → project default → error.

    Normalizes to BCP-47 using ``langcodes``.
    """
    raw = options.target_language

    # Fallback to project default.
    if not raw and page.chapter and page.chapter.project:
        raw = getattr(page.chapter.project, "target_language", None) or None

    if not raw:
        raise TranslationLanguageResolutionError(
            "target_language not provided and no project default available"
        )

    # Normalize to BCP-47.
    try:
        tag = langcodes.standardize_tag(raw)
    except Exception:
        tag = raw  # Accept as-is if langcodes can't parse it.

    return tag


async def _check_duplicate_translate_run(
    db: AsyncSession,
    page_id: uuid.UUID,
    effective_language: str,
    force: bool = False,
) -> None:
    """Reject if a pending/running translate run exists for same page+language.
    
    If force=True, marks existing runs as failed (Orphaned) and allows the new run.
    If a job is older than 15 minutes, it is automatically considered orphaned.
    """
    from sqlalchemy import and_, or_
    from datetime import datetime, timezone, timedelta

    stmt = (
        select(PipelineRun)
        .where(
            and_(
                PipelineRun.page_id == page_id,
                PipelineRun.stage == "translate",
                PipelineRun.status.in_(["pending", "running"]),
            )
        )
    )
    result = await db.execute(stmt)
    existing_runs = result.scalars().all()

    if not existing_runs:
        return

    stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    active_orphans = []
    truly_active = []

    for run in existing_runs:
        is_stale = run.created_at < stale_threshold
        if force or is_stale:
            active_orphans.append(run)
        else:
            truly_active.append(run)

    # Clean up orphans
    for run in active_orphans:
        reason = "Forced retry" if force else "Stale/Orphaned (Auto-cleaned)"
        run.status = "failed"
        run.error_message = f"Orphaned: {reason}"
        run.finished_at = datetime.now(timezone.utc)
        logger.info(f"Marked run {run.id} as failed ({reason})")

    if truly_active and not force:
        existing = truly_active[0]
        raise TranslationDuplicateRunError(
            f"Active translate run {existing.id} already exists for page {page_id}. "
            "Wait for it to finish or use force=True."
        )


# Module-level singleton
job_dispatcher = JobDispatcher()
