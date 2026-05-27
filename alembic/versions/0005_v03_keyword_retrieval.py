"""add v0.3 keyword retrieval search text

Revision ID: 0005_v03_keyword_retrieval
Revises: 0004_v02_model_management
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_v03_keyword_retrieval"
down_revision: str | None = "0004_v02_model_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("search_text", sa.Text(), nullable=True))
    op.execute(
        "UPDATE chunks SET search_text = trim(coalesce(context_header, '') || ' ' || coalesce(content, '')) "
        "WHERE search_text IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_search_text_fts "
        "ON chunks USING GIN (to_tsvector('simple', coalesce(search_text, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_text_fts")
    op.drop_column("chunks", "search_text")
