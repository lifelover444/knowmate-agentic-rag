"""add v0.9 paradedb bm25 keyword index

Revision ID: 0017_v09_paradedb_bm25
Revises: 0016_task032_faq_recommended
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_v09_paradedb_bm25"
down_revision: str | None = "0016_task032_faq_recommended"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_text_fts")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_paradedb_bm25 ON chunks
        USING bm25 (
            id,
            search_text,
            content,
            knowledge_base_id,
            knowledge_id,
            chunk_type,
            is_enabled,
            deleted_at,
            metadata,
            context_header
        )
        WITH (key_field='id')
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_chunks_paradedb_bm25")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_search_text_fts "
        "ON chunks USING GIN (to_tsvector('simple', coalesce(search_text, '')))"
    )
