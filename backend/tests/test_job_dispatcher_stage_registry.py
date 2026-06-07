from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.job import InpaintOptions
from app.services.job_dispatcher import _STAGE_HANDLERS
from app.services import job_dispatcher


def test_stage_registry_includes_new_backend_services() -> None:
    assert "ocr" in _STAGE_HANDLERS
    assert "reading_order" in _STAGE_HANDLERS
    assert "inpaint" in _STAGE_HANDLERS
    assert "helper_grounded" in _STAGE_HANDLERS


async def test_ocr_handler_runs_reading_order_before_ocr() -> None:
    db = object()
    run = SimpleNamespace(id="run-id")
    page = SimpleNamespace(id="page-id")

    call_order: list[str] = []

    reading_order_mock = AsyncMock(return_value={"panel_count": 2, "assigned_item_count": 3})
    ocr_mock = AsyncMock(return_value={"processed_regions": 3, "failed_regions": 0})

    async def wrapped_reading_order(*args, **kwargs):
        call_order.append("reading_order")
        return await reading_order_mock(*args, **kwargs)

    async def wrapped_ocr(*args, **kwargs):
        call_order.append("ocr")
        return await ocr_mock(*args, **kwargs)

    original_reading_order = job_dispatcher.reading_order_service.run_for_page
    original_ocr = job_dispatcher.ocr_service.run_for_page
    job_dispatcher.reading_order_service.run_for_page = wrapped_reading_order
    job_dispatcher.ocr_service.run_for_page = wrapped_ocr
    try:
        metrics = await job_dispatcher._handle_ocr(db, run, page)
    finally:
        job_dispatcher.reading_order_service.run_for_page = original_reading_order
        job_dispatcher.ocr_service.run_for_page = original_ocr

    assert call_order == ["reading_order", "ocr"]
    assert metrics == {
        "reading_order": {"panel_count": 2, "assigned_item_count": 3},
        "ocr": {"processed_regions": 3, "failed_regions": 0},
    }


async def test_inpaint_handler_passes_options_from_run_input_params() -> None:
    db = object()
    run = SimpleNamespace(
        id="run-id",
        input_params_json={
            "inpaint_options": {
                "method": "ns",
                "radius": 6,
                "ai_expand_strength": 0.4,
                "balloon_safe_inset_mode": "manual",
                "balloon_safe_inset_px": 4.0,
                "clip_fallback_mode": "inset_bbox",
            }
        },
    )
    page = SimpleNamespace(id="page-id")

    captured_options: list[InpaintOptions] = []

    async def fake_run_for_page(*_args, **kwargs):
        captured_options.append(kwargs["options"])
        return {"ok": True}

    original_inpaint = job_dispatcher.inpaint_page_service.run_for_page
    job_dispatcher.inpaint_page_service.run_for_page = fake_run_for_page
    try:
        metrics = await job_dispatcher._handle_inpaint(db, run, page)
    finally:
        job_dispatcher.inpaint_page_service.run_for_page = original_inpaint

    assert metrics == {"ok": True}
    assert len(captured_options) == 1
    assert captured_options[0].method == "ns"
    assert captured_options[0].radius == 6
