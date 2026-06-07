"""add render font weight to page_texts

Revision ID: 7b4c8d9e0f12
Revises: 6292332f631a
Create Date: 2026-05-02 01:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b4c8d9e0f12"
down_revision = "6292332f631a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("page_texts") as batch_op:
        batch_op.add_column(sa.Column("render_font_weight", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("page_texts") as batch_op:
        batch_op.drop_column("render_font_weight")
