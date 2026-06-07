"""Add translation memory entries table with FTS + vector support.

Revision ID: c9f3e2a1b4d8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c9f3e2a1b4d8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "translation_memory_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("source_term", sa.Text(), nullable=False),
        sa.Column("preferred_translation", sa.Text(), nullable=False),
        sa.Column("scope_chapter", sa.Integer(), nullable=True),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("normalized_source_term", sa.Text(), nullable=False),
        sa.Column(
            "normalized_aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("embedding", sa.VARCHAR(), nullable=True),
        sa.Column("search_document", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entry_type IN ('character', 'attack', 'place', 'organization')",
            name="translation_memory_entry_type_check",
        ),
        sa.CheckConstraint(
            "scope_chapter IS NULL OR scope_chapter >= 1",
            name="translation_memory_scope_chapter_check",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f(
                "fk_translation_memory_entries_project_id_projects",
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_memory_entries")),
    )
    op.execute(
        "ALTER TABLE translation_memory_entries "
        "ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector"
    )

    op.create_index(
        op.f("ix_translation_memory_entries_project_id"),
        "translation_memory_entries",
        ["project_id"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_translation_memory_entries_scope_term "
        "ON translation_memory_entries "
        "(project_id, COALESCE(scope_chapter, -1), entry_type, normalized_source_term)"
    )
    op.create_index(
        "ix_translation_memory_entries_search_document",
        "translation_memory_entries",
        ["search_document"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_translation_memory_entries_aliases",
        "translation_memory_entries",
        ["aliases"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_translation_memory_entries_embedding_ivfflat "
        "ON translation_memory_entries USING ivfflat "
        "(embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_translation_memory_search_document()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_document := to_tsvector(
                'simple',
                concat_ws(
                    ' ',
                    NEW.source_term,
                    NEW.preferred_translation,
                    array_to_string(COALESCE(NEW.aliases, '{}'::text[]), ' '),
                    COALESCE(NEW.notes, '')
                )
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_refresh_translation_memory_search_document
        BEFORE INSERT OR UPDATE OF source_term, preferred_translation, aliases, notes
        ON translation_memory_entries
        FOR EACH ROW
        EXECUTE FUNCTION refresh_translation_memory_search_document();
        """
    )
    op.execute(
        """
        UPDATE translation_memory_entries
        SET search_document = to_tsvector(
            'simple',
            concat_ws(
                ' ',
                source_term,
                preferred_translation,
                array_to_string(COALESCE(aliases, '{}'::text[]), ' '),
                COALESCE(notes, '')
            )
        );
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_translation_memory_entries_embedding_ivfflat"
    )
    op.drop_index(
        "ix_translation_memory_entries_aliases",
        table_name="translation_memory_entries",
    )
    op.drop_index(
        "ix_translation_memory_entries_search_document",
        table_name="translation_memory_entries",
    )
    op.drop_index(
        "uq_translation_memory_entries_scope_term",
        table_name="translation_memory_entries",
    )
    op.drop_index(
        op.f("ix_translation_memory_entries_project_id"),
        table_name="translation_memory_entries",
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_refresh_translation_memory_search_document "
        "ON translation_memory_entries"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS refresh_translation_memory_search_document"
    )
    op.drop_table("translation_memory_entries")
