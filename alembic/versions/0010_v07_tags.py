"""add v0.7 knowledge tags

Revision ID: 0010_v07_tags
Revises: 0009_v06_chat_sessions
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_v07_tags"
down_revision: str | None = "0009_v06_chat_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "knowledge_base_id", "name", name="uq_knowledge_tags_tenant_kb_name"),
    )
    op.create_index("ix_knowledge_tags_tenant_id", "knowledge_tags", ["tenant_id"])
    op.create_index("ix_knowledge_tags_knowledge_base_id", "knowledge_tags", ["knowledge_base_id"])
    op.create_index(
        "ix_knowledge_tags_tenant_kb_sort",
        "knowledge_tags",
        ["tenant_id", "knowledge_base_id", "sort_order", "created_at"],
    )

    op.add_column("knowledges", sa.Column("tag_id", sa.String(length=36), nullable=True))
    op.add_column("faq_entries", sa.Column("tag_id", sa.String(length=36), nullable=True))
    op.add_column("chunks", sa.Column("tag_id", sa.String(length=36), nullable=True))
    op.create_index("ix_knowledges_tag_id", "knowledges", ["tag_id"])
    op.create_index("ix_faq_entries_tag_id", "faq_entries", ["tag_id"])
    op.create_index("ix_chunks_tag_id", "chunks", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_tag_id", table_name="chunks")
    op.drop_index("ix_faq_entries_tag_id", table_name="faq_entries")
    op.drop_index("ix_knowledges_tag_id", table_name="knowledges")
    op.drop_column("chunks", "tag_id")
    op.drop_column("faq_entries", "tag_id")
    op.drop_column("knowledges", "tag_id")
    op.drop_index("ix_knowledge_tags_tenant_kb_sort", table_name="knowledge_tags")
    op.drop_index("ix_knowledge_tags_knowledge_base_id", table_name="knowledge_tags")
    op.drop_index("ix_knowledge_tags_tenant_id", table_name="knowledge_tags")
    op.drop_table("knowledge_tags")
