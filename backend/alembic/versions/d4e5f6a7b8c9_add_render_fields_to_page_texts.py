"""add render fields to page_texts

Revision ID: d4e5f6a7b8c9
Revises: c9f3e2a1b4d8
Create Date: 2026-04-25 21:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c9f3e2a1b4d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("page_texts") as batch_op:
        batch_op.add_column(sa.Column("render_scale", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("render_color", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("render_font_family", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("page_texts") as batch_op:
        batch_op.drop_column("render_font_family")
        batch_op.drop_column("render_color")
        batch_op.drop_column("render_scale")
