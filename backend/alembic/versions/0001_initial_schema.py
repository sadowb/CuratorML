"""Initial ERD schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-03-28 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_language", sa.String(length=100), nullable=False),
        sa.Column("target_language", sa.String(length=100), nullable=False),
        sa.Column("reading_direction", sa.String(length=10), nullable=False),
        sa.Column("project_status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("enable_ocr", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("require_qc", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_projects_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_name"), "projects", ["name"], unique=False)
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)

    op.create_table(
        "project_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_kind", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_files_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_files")),
    )
    op.create_index(op.f("ix_project_files_project_id"), "project_files", ["project_id"], unique=False)

    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("chapter_status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_chapters_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapters")),
    )
    op.create_index(op.f("ix_chapters_project_id"), "chapters", ["project_id"], unique=False)

    op.create_table(
        "chapter_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_kind", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], name=op.f("fk_chapter_files_chapter_id_chapters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapter_files")),
    )
    op.create_index(op.f("ix_chapter_files_chapter_id"), "chapter_files", ["chapter_id"], unique=False)

    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("current_stage", sa.String(length=50), server_default="uploaded", nullable=False),
        sa.Column("review_status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], name=op.f("fk_pages_chapter_id_chapters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
    )
    op.create_index(op.f("ix_pages_chapter_id"), "pages", ["chapter_id"], unique=False)

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("model_version", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_pipeline_runs_page_id_pages"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], name=op.f("fk_pipeline_runs_triggered_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_runs")),
    )
    op.create_index(op.f("ix_pipeline_runs_page_id"), "pipeline_runs", ["page_id"], unique=False)
    op.create_index(op.f("ix_pipeline_runs_triggered_by_user_id"), "pipeline_runs", ["triggered_by_user_id"], unique=False)

    op.create_table(
        "page_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_kind", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_page_files_page_id_pages"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], name=op.f("fk_page_files_pipeline_run_id_pipeline_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_files")),
    )
    op.create_index(op.f("ix_page_files_page_id"), "page_files", ["page_id"], unique=False)
    op.create_index(op.f("ix_page_files_pipeline_run_id"), "page_files", ["pipeline_run_id"], unique=False)

    op.create_table(
        "page_regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_region_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("region_kind", sa.String(length=60), nullable=False),
        sa.Column("polygon_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bbox_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reading_order", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_page_regions_created_by_user_id_users")),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_page_regions_page_id_pages"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_region_id"], ["page_regions.id"], name=op.f("fk_page_regions_parent_region_id_page_regions")),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], name=op.f("fk_page_regions_pipeline_run_id_pipeline_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_regions")),
    )
    op.create_index(op.f("ix_page_regions_created_by_user_id"), "page_regions", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_page_regions_page_id"), "page_regions", ["page_id"], unique=False)
    op.create_index(op.f("ix_page_regions_parent_region_id"), "page_regions", ["parent_region_id"], unique=False)
    op.create_index(op.f("ix_page_regions_pipeline_run_id"), "page_regions", ["pipeline_run_id"], unique=False)

    op.create_table(
        "page_texts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ocr_text_raw", sa.Text(), nullable=True),
        sa.Column("ocr_text_corrected", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("context_notes", sa.Text(), nullable=True),
        sa.Column("translation_draft", sa.Text(), nullable=True),
        sa.Column("translation_corrected", sa.Text(), nullable=True),
        sa.Column("display_text_final", sa.Text(), nullable=True),
        sa.Column("translation_status", sa.String(length=40), server_default="draft", nullable=False),
        sa.Column("approved_for_inpaint", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], name=op.f("fk_page_texts_pipeline_run_id_pipeline_runs")),
        sa.ForeignKeyConstraint(["region_id"], ["page_regions.id"], name=op.f("fk_page_texts_region_id_page_regions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_texts")),
    )
    op.create_index(op.f("ix_page_texts_pipeline_run_id"), "page_texts", ["pipeline_run_id"], unique=False)
    op.create_index(op.f("ix_page_texts_region_id"), "page_texts", ["region_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_page_texts_region_id"), table_name="page_texts")
    op.drop_index(op.f("ix_page_texts_pipeline_run_id"), table_name="page_texts")
    op.drop_table("page_texts")

    op.drop_index(op.f("ix_page_regions_pipeline_run_id"), table_name="page_regions")
    op.drop_index(op.f("ix_page_regions_parent_region_id"), table_name="page_regions")
    op.drop_index(op.f("ix_page_regions_page_id"), table_name="page_regions")
    op.drop_index(op.f("ix_page_regions_created_by_user_id"), table_name="page_regions")
    op.drop_table("page_regions")

    op.drop_index(op.f("ix_page_files_pipeline_run_id"), table_name="page_files")
    op.drop_index(op.f("ix_page_files_page_id"), table_name="page_files")
    op.drop_table("page_files")

    op.drop_index(op.f("ix_pipeline_runs_triggered_by_user_id"), table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_page_id"), table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    op.drop_index(op.f("ix_pages_chapter_id"), table_name="pages")
    op.drop_table("pages")

    op.drop_index(op.f("ix_chapter_files_chapter_id"), table_name="chapter_files")
    op.drop_table("chapter_files")

    op.drop_index(op.f("ix_chapters_project_id"), table_name="chapters")
    op.drop_table("chapters")

    op.drop_index(op.f("ix_project_files_project_id"), table_name="project_files")
    op.drop_table("project_files")

    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_name"), table_name="projects")
    op.drop_table("projects")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
