"""task027 rendered context

Revision ID: 0014_task027_rendered_context
Revises: 0013_v07_faq_similar_indexing
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_task027_rendered_context"
down_revision: str | None = "0013_v07_faq_similar_indexing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("rendered_context", sa.Text(), nullable=True))
    op.add_column("chat_messages", sa.Column("prompt_context_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "prompt_context_summary")
    op.drop_column("chat_messages", "rendered_context")
