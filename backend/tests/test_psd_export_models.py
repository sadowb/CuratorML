from __future__ import annotations

import uuid

import pytest

from app.services.psd_export.models import (
    CanvasSize,
    PageExportDocument,
    PageExportOptions,
    PageImageAsset,
    TranslatedTextBlock,
)


def test_translated_text_block_requires_hex_color() -> None:
    with pytest.raises(ValueError):
        TranslatedTextBlock(
            id=uuid.uuid4(),
            name="Text_1",
            translated_text="Hello",
            x=10,
            y=20,
            width=100,
            height=60,
            group="Dialogue",
            font_size=24,
            color="black",
            visibility=True,
        )


def test_page_export_document_min_contract() -> None:
    page_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    project_id = uuid.uuid4()
    original_file_id = uuid.uuid4()

    document = PageExportDocument(
        export_id=uuid.uuid4(),
        page_id=page_id,
        chapter_id=chapter_id,
        project_id=project_id,
        canvas=CanvasSize(width=1000, height=1400),
        original_image=PageImageAsset(
            file_id=original_file_id,
            file_kind="original",
            file_path="project_x/chapter_y/page_z/original.png",
            mime_type="image/png",
            width=1000,
            height=1400,
        ),
        options=PageExportOptions(),
    )

    assert document.page_id == page_id
    assert document.canvas.width == 1000
    assert document.panel_masks == []
