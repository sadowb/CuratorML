"""drop approved_for_inpaint from page_texts

Revision ID: 30743a54adda
Revises: ec9092c47cfe
Create Date: 2026-04-08 00:37:56.427536

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '30743a54adda'
down_revision = 'ec9092c47cfe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("page_texts") as batch_op:
        batch_op.drop_column("approved_for_inpaint")


def downgrade() -> None:
    with op.batch_alter_table("page_texts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "approved_for_inpaint",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )