"""add v0.5 FAQ knowledge base fields

Revision ID: 0007_v05_faq_kb_type
Revises: 0006_v05_tasks
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_v05_faq_kb_type"
down_revision: str | None = "0006_v05_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("kb_type", sa.String(length=32), nullable=False, server_default="document"),
    )
    op.add_column("knowledge_bases", sa.Column("indexing_strategy", sa.JSON(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("vector_store_id", sa.String(length=36), nullable=True))
    op.create_index("ix_knowledge_bases_kb_type", "knowledge_bases", ["kb_type"])

    op.add_column("knowledges", sa.Column("source_type", sa.String(length=50), nullable=False, server_default="file"))
    op.create_index("ix_knowledges_source_type", "knowledges", ["source_type"])

    op.create_table(
        "faq_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_id", sa.String(length=36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faq_entries_tenant_id", "faq_entries", ["tenant_id"])
    op.create_index("ix_faq_entries_knowledge_base_id", "faq_entries", ["knowledge_base_id"])
    op.create_index("ix_faq_entries_knowledge_id", "faq_entries", ["knowledge_id"])
    op.create_index("ix_faq_entries_enabled", "faq_entries", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_faq_entries_enabled", table_name="faq_entries")
    op.drop_index("ix_faq_entries_knowledge_id", table_name="faq_entries")
    op.drop_index("ix_faq_entries_knowledge_base_id", table_name="faq_entries")
    op.drop_index("ix_faq_entries_tenant_id", table_name="faq_entries")
    op.drop_table("faq_entries")

    op.drop_index("ix_knowledges_source_type", table_name="knowledges")
    op.drop_column("knowledges", "source_type")

    op.drop_index("ix_knowledge_bases_kb_type", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "vector_store_id")
    op.drop_column("knowledge_bases", "indexing_strategy")
    op.drop_column("knowledge_bases", "kb_type")
