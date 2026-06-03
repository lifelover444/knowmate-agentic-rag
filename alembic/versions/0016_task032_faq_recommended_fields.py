"""task032 faq recommended fields

Revision ID: 0016_task032_faq_recommended_fields
Revises: 0015_task031_faq_import_results
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_task032_faq_recommended"
down_revision: str | None = "0015_task031_faq_import_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "faq_entries",
        sa.Column("is_recommended", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_faq_entries_is_recommended", "faq_entries", ["is_recommended"])
    op.alter_column("faq_entries", "is_recommended", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_faq_entries_is_recommended", table_name="faq_entries")
    op.drop_column("faq_entries", "is_recommended")
