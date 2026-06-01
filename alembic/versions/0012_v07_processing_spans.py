"""v0.7 processing spans

Revision ID: 0012_v07_processing_spans
Revises: 0011_v07_kb_pins
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_v07_processing_spans"
down_revision: str | None = "0011_v07_kb_pins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_processing_spans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_id", sa.String(length=36), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("span_id", sa.String(length=64), nullable=False),
        sa.Column("parent_span_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_id"], ["knowledges.id"]),
        sa.UniqueConstraint("knowledge_id", "attempt", "span_id", name="uq_processing_spans_knowledge_attempt_span"),
    )
    op.create_index("ix_processing_spans_tenant_id", "knowledge_processing_spans", ["tenant_id"])
    op.create_index("ix_processing_spans_knowledge_id", "knowledge_processing_spans", ["knowledge_id"])
    op.create_index(
        "ix_processing_spans_knowledge_attempt",
        "knowledge_processing_spans",
        ["knowledge_id", "attempt"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_spans_knowledge_attempt", table_name="knowledge_processing_spans")
    op.drop_index("ix_processing_spans_knowledge_id", table_name="knowledge_processing_spans")
    op.drop_index("ix_processing_spans_tenant_id", table_name="knowledge_processing_spans")
    op.drop_table("knowledge_processing_spans")
