"""Add input_params_json to pipeline_runs

Revision ID: a1b2c3d4e5f6
Revises: 5a9b6a2d8f11
Create Date: 2026-04-16 22:30:00.000000+01:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5a9b6a2d8f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("input_params_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_runs", "input_params_json")
