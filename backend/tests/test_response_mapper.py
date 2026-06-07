from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.response_mapper import (
    build_original_file_url,
    build_page_file_url,
    map_page_detail,
    map_paginated_page_summaries,
)


def test_map_paginated_page_summaries_sets_original_file_url() -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()
    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        page_number=1,
        current_stage="uploaded",
        review_status="pending",
        created_at=now,
        updated_at=now,
        files=[SimpleNamespace(file_kind="original", is_current=True)],
    )

    response = map_paginated_page_summaries(
        [page],
        total=1,
        page=1,
        page_size=25,
        project_id=project_id,
    )

    assert len(response.items) == 1
    assert response.items[0].original_file_url == build_original_file_url(project_id, chapter_id, page_id)
    assert response.pagination.total == 1
    assert response.pagination.has_next is False


def test_map_page_detail_sorts_texts_and_maps_urls() -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()

    text_id_a = uuid.UUID("00000000-0000-0000-0000-000000000002")
    text_id_b = uuid.UUID("00000000-0000-0000-0000-000000000001")
    region_id = uuid.uuid4()

    text_a = SimpleNamespace(
        id=text_id_a,
        region_id=region_id,
        pipeline_run_id=None,
        ocr_text_raw="raw-a",
        ocr_text_corrected="corr-a",
        ocr_confidence=0.9,
        context_notes=None,
        translation_draft=None,
        translation_corrected=None,
        display_text_final=None,
        translation_status="draft",
        
        created_at=now,
        updated_at=now,
    )
    text_b = SimpleNamespace(
        id=text_id_b,
        region_id=region_id,
        pipeline_run_id=None,
        ocr_text_raw="raw-b",
        ocr_text_corrected="corr-b",
        ocr_confidence=0.95,
        context_notes=None,
        translation_draft=None,
        translation_corrected=None,
        display_text_final=None,
        translation_status="draft",
        
        created_at=now,
        updated_at=now,
    )
    region = SimpleNamespace(
        id=region_id,
        page_id=page_id,
        parent_region_id=None,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="text",
        polygon_json=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
        bbox_json=[0.0, 0.0, 10.0, 10.0],
        confidence=0.95,
        reading_order=1,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
        texts=[text_a, text_b],
    )

    page_file = SimpleNamespace(
        id=uuid.uuid4(),
        page_id=page_id,
        pipeline_run_id=None,
        file_kind="original",
        file_path="project/chapter/page/original.jpg",
        mime_type="image/jpeg",
        width=None,
        height=None,
        is_current=True,
        created_at=now,
    )
    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        page_number=1,
        current_stage="uploaded",
        review_status="pending",
        created_at=now,
        updated_at=now,
        files=[page_file],
        regions=[region],
        chapter=SimpleNamespace(project_id=project_id),
    )

    detail = map_page_detail(page)

    assert detail.original_file_url == build_original_file_url(project_id, chapter_id, page_id)
    assert [text.id for text in detail.texts] == [text_id_b, text_id_a]
    assert len(detail.regions) == 1
    assert detail.regions[0].id == region_id
    assert detail.regions[0].polygon_json is not None


def test_map_page_detail_sets_urls_for_current_derived_files() -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()

    original_file = SimpleNamespace(
        id=uuid.uuid4(),
        page_id=page_id,
        pipeline_run_id=None,
        file_kind="original",
        file_path="project/chapter/page/original.jpg",
        mime_type="image/jpeg",
        width=None,
        height=None,
        is_current=True,
        created_at=now,
    )
    inpainted_file = SimpleNamespace(
        id=uuid.uuid4(),
        page_id=page_id,
        pipeline_run_id=None,
        file_kind="inpainted",
        file_path="project/chapter/page/inpainted.jpg",
        mime_type="image/jpeg",
        width=None,
        height=None,
        is_current=True,
        created_at=now,
    )
    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        page_number=1,
        current_stage="uploaded",
        review_status="pending",
        created_at=now,
        updated_at=now,
        files=[original_file, inpainted_file],
        regions=[],
        chapter=SimpleNamespace(project_id=project_id),
    )

    detail = map_page_detail(page)

    urls = {item.file_kind: item.url for item in detail.files}
    assert urls["original"] == build_original_file_url(project_id, chapter_id, page_id)
    assert urls["inpainted"] == build_page_file_url(project_id, chapter_id, page_id, "inpainted")


def test_map_page_detail_excludes_texts_from_inactive_regions() -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()

    active_region_id = uuid.uuid4()
    inactive_region_id = uuid.uuid4()

    active_text = SimpleNamespace(
        id=uuid.uuid4(),
        region_id=active_region_id,
        pipeline_run_id=None,
        ocr_text_raw="active",
        ocr_text_corrected=None,
        ocr_confidence=0.9,
        context_notes=None,
        translation_draft=None,
        translation_corrected=None,
        display_text_final=None,
        translation_status="draft",
        created_at=now,
        updated_at=now,
    )
    inactive_text = SimpleNamespace(
        id=uuid.uuid4(),
        region_id=inactive_region_id,
        pipeline_run_id=None,
        ocr_text_raw="inactive",
        ocr_text_corrected=None,
        ocr_confidence=0.9,
        context_notes=None,
        translation_draft=None,
        translation_corrected=None,
        display_text_final=None,
        translation_status="draft",
        created_at=now,
        updated_at=now,
    )

    active_region = SimpleNamespace(
        id=active_region_id,
        page_id=page_id,
        parent_region_id=None,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="text",
        polygon_json=None,
        bbox_json=[0.0, 0.0, 10.0, 10.0],
        confidence=0.95,
        reading_order=1,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
        texts=[active_text],
    )
    inactive_region = SimpleNamespace(
        id=inactive_region_id,
        page_id=page_id,
        parent_region_id=None,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="text",
        polygon_json=None,
        bbox_json=[0.0, 0.0, 10.0, 10.0],
        confidence=0.95,
        reading_order=2,
        origin="mask_inference",
        is_active=False,
        created_at=now,
        updated_at=now,
        texts=[inactive_text],
    )

    original_file = SimpleNamespace(
        id=uuid.uuid4(),
        page_id=page_id,
        pipeline_run_id=None,
        file_kind="original",
        file_path="project/chapter/page/original.jpg",
        mime_type="image/jpeg",
        width=None,
        height=None,
        is_current=True,
        created_at=now,
    )
    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        page_number=1,
        current_stage="ocr",
        review_status="pending",
        created_at=now,
        updated_at=now,
        files=[original_file],
        regions=[active_region, inactive_region],
        chapter=SimpleNamespace(project_id=project_id),
    )

    detail = map_page_detail(page)

    assert len(detail.texts) == 1
    assert detail.texts[0].ocr_text_raw == "active"


def test_map_page_detail_sorts_texts_by_panel_and_item_reading_order() -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    page_id = uuid.uuid4()

    panel_a_id = uuid.uuid4()
    panel_b_id = uuid.uuid4()
    text_a_id = uuid.uuid4()
    text_b_id = uuid.uuid4()

    panel_a = SimpleNamespace(
        id=panel_a_id,
        page_id=page_id,
        parent_region_id=None,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="panel",
        polygon_json=None,
        bbox_json=[0.0, 0.0, 50.0, 50.0],
        confidence=0.9,
        reading_order=1,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
        texts=[],
    )
    panel_b = SimpleNamespace(
        id=panel_b_id,
        page_id=page_id,
        parent_region_id=None,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="panel",
        polygon_json=None,
        bbox_json=[60.0, 0.0, 120.0, 50.0],
        confidence=0.9,
        reading_order=2,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
        texts=[],
    )

    text_a = SimpleNamespace(
        id=text_a_id,
        region_id=uuid.uuid4(),
        pipeline_run_id=None,
        ocr_text_raw="panel-a-text",
        ocr_text_corrected=None,
        ocr_confidence=0.9,
        context_notes=None,
        translation_draft=None,
        translation_corrected=None,
        display_text_final=None,
        translation_status="draft",
        created_at=now,
        updated_at=now,
    )
    text_b = SimpleNamespace(
        id=text_b_id,
        region_id=uuid.uuid4(),
        pipeline_run_id=None,
        ocr_text_raw="panel-b-text",
        ocr_text_corrected=None,
        ocr_confidence=0.9,
        context_notes=None,
        translation_draft=None,
        translation_corrected=None,
        display_text_final=None,
        translation_status="draft",
        created_at=now,
        updated_at=now,
    )

    text_region_b = SimpleNamespace(
        id=text_b.region_id,
        page_id=page_id,
        parent_region_id=panel_b_id,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="text",
        polygon_json=None,
        bbox_json=[70.0, 10.0, 90.0, 20.0],
        confidence=0.9,
        reading_order=1,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
        texts=[text_b],
    )
    text_region_a = SimpleNamespace(
        id=text_a.region_id,
        page_id=page_id,
        parent_region_id=panel_a_id,
        pipeline_run_id=None,
        created_by_user_id=None,
        region_kind="text",
        polygon_json=None,
        bbox_json=[10.0, 10.0, 30.0, 20.0],
        confidence=0.9,
        reading_order=1,
        origin="mask_inference",
        is_active=True,
        created_at=now,
        updated_at=now,
        texts=[text_a],
    )

    page = SimpleNamespace(
        id=page_id,
        chapter_id=chapter_id,
        page_number=1,
        current_stage="ocr",
        review_status="pending",
        created_at=now,
        updated_at=now,
        files=[],
        regions=[text_region_b, panel_b, text_region_a, panel_a],
        chapter=SimpleNamespace(project_id=project_id),
    )

    detail = map_page_detail(page)
    assert [text.ocr_text_raw for text in detail.texts] == [
        "panel-a-text",
        "panel-b-text",
    ]
