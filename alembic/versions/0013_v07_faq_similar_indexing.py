"""v0.7 FAQ similar questions and index config

Revision ID: 0013_v07_faq_similar_indexing
Revises: 0012_v07_processing_spans
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_v07_faq_similar_indexing"
down_revision: str | None = "0012_v07_processing_spans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("faq_config", sa.JSON(), nullable=True))
    op.add_column("faq_entries", sa.Column("similar_questions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("faq_entries", "similar_questions")
    op.drop_column("knowledge_bases", "faq_config")
