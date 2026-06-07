"""add page text regions active view

Revision ID: 5a9b6a2d8f11
Revises: 30743a54adda
Create Date: 2026-04-16 18:20:00

"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "5a9b6a2d8f11"
down_revision = "30743a54adda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW public.v_page_text_regions_active AS
        SELECT
            pt.id AS page_text_id,
            pr.id AS region_id,
            pr.page_id AS page_id,
            pr.reading_order AS reading_order,
            pt.ocr_text_raw AS ocr_text_raw,
            pt.ocr_text_corrected AS ocr_text_corrected,
            pt.translation_draft AS translation_draft
        FROM public.page_regions pr
        LEFT JOIN public.page_texts pt
            ON pt.region_id = pr.id
        WHERE pr.region_kind = 'text'
          AND pr.is_active = true
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public.v_page_text_regions_active")
