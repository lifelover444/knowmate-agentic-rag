"""add v0.7 knowledge base pins

Revision ID: 0011_v07_kb_pins
Revises: 0010_v07_tags
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_v07_kb_pins"
down_revision: str | None = "0010_v07_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_pins",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "knowledge_base_id", name="uq_kb_pins_tenant_kb"),
    )
    op.create_index("ix_knowledge_base_pins_tenant_id", "knowledge_base_pins", ["tenant_id"])
    op.create_index("ix_knowledge_base_pins_knowledge_base_id", "knowledge_base_pins", ["knowledge_base_id"])
    op.create_index("ix_kb_pins_tenant_pinned", "knowledge_base_pins", ["tenant_id", "pinned_at"])


def downgrade() -> None:
    op.drop_index("ix_kb_pins_tenant_pinned", table_name="knowledge_base_pins")
    op.drop_index("ix_knowledge_base_pins_knowledge_base_id", table_name="knowledge_base_pins")
    op.drop_index("ix_knowledge_base_pins_tenant_id", table_name="knowledge_base_pins")
    op.drop_table("knowledge_base_pins")
