from __future__ import annotations

import uuid

from app.models.page import Page
from app.models.page_file import PageFile
from app.models.page_text import PageText
from app.schemas.page import (
    PageDetailOut,
    PageFileOut,
    PagePaginationOut,
    PageSummaryOut,
    PageTextOut,
    PageUploadItemOut,
    PageUploadResponse,
    PaginatedPageSummaryOut,
)
from app.schemas.page_region import PageRegionOut
from app.schemas.project import ProjectListItem


def build_original_file_url(project_id: uuid.UUID, chapter_id: uuid.UUID, page_id: uuid.UUID) -> str:
    return build_page_file_url(project_id, chapter_id, page_id, "original")


def build_page_file_url(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    page_id: uuid.UUID,
    file_kind: str,
) -> str:
    return f"/api/v1/storage/{project_id}/{chapter_id}/{page_id}/{file_kind}"


def map_project_list_items(rows: list[tuple]) -> list[ProjectListItem]:
    items: list[ProjectListItem] = []
    for project, chapter_count, page_count in rows:
        model = ProjectListItem.model_validate(project)
        model.chapter_count = int(chapter_count or 0)
        model.page_count = int(page_count or 0)
        items.append(model)
    return items


def map_page_summary(page: Page, project_id: uuid.UUID) -> PageSummaryOut:
    model = PageSummaryOut.model_validate(page)
    original = next((file for file in page.files if file.file_kind == "original" and file.is_current), None)
    if original is not None:
        model.original_file_url = build_original_file_url(project_id, page.chapter_id, page.id)
    return model


def map_paginated_page_summaries(
    page_items: list[Page],
    *,
    total: int,
    page: int,
    page_size: int,
    project_id: uuid.UUID,
) -> PaginatedPageSummaryOut:
    items = [map_page_summary(page_item, project_id) for page_item in page_items]
    has_prev = page > 1
    has_next = (page * page_size) < total
    return PaginatedPageSummaryOut(
        items=items,
        pagination=PagePaginationOut(
            page=page,
            page_size=page_size,
            total=total,
            has_next=has_next,
            has_prev=has_prev,
        ),
    )


def map_page_upload_response(
    records: list[tuple[Page, PageFile]],
    *,
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> PageUploadResponse:
    items: list[PageUploadItemOut] = []
    for page, page_file in records:
        page_summary = PageSummaryOut.model_validate(page)
        page_summary.original_file_url = build_original_file_url(project_id, chapter_id, page.id)

        file_summary = PageFileOut.model_validate(page_file)
        file_summary.url = page_summary.original_file_url

        items.append(PageUploadItemOut(page=page_summary, file=file_summary))
    return PageUploadResponse(items=items)


def map_page_detail(page: Page) -> PageDetailOut:
    detail = PageDetailOut(
        id=page.id,
        chapter_id=page.chapter_id,
        page_number=page.page_number,
        current_stage=page.current_stage,
        review_status=page.review_status,
        created_at=page.created_at,
        updated_at=page.updated_at,
        original_file_url=None,
        files=[],
        texts=[],
        regions=[],
    )

    for file in page.files:
        file_out = PageFileOut.model_validate(file)
        if file.is_current:
            file_out.url = build_page_file_url(
                page.chapter.project_id,
                page.chapter_id,
                page.id,
                file.file_kind,
            )
            if file.file_kind == "original":
                detail.original_file_url = file_out.url
        detail.files.append(file_out)

    region_by_id = {region.id: region for region in page.regions}
    texts: list[PageText] = []
    for region in page.regions:
        if not region.is_active or region.region_kind != "text":
            continue
        texts.extend(region.texts)

    def text_sort_key(text: PageText) -> tuple:
        region = region_by_id.get(text.region_id)
        panel_order: int | None = None
        item_order: int | None = None

        if region is not None:
            item_order = region.reading_order
            if region.parent_region_id is not None:
                parent_region = region_by_id.get(region.parent_region_id)
                if parent_region is not None and parent_region.region_kind == "panel":
                    panel_order = parent_region.reading_order

        return (
            panel_order is None,
            panel_order or 0,
            item_order is None,
            item_order or 0,
            text.created_at,
            str(text.id),
        )

    texts.sort(key=text_sort_key)
    detail.texts = [PageTextOut.model_validate(text) for text in texts]
    detail.regions = [PageRegionOut.model_validate(region) for region in page.regions]
    detail.regions.sort(key=lambda item: str(item.id))
    return detail
