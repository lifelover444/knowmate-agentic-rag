"""add v0.5 processing tasks

Revision ID: 0006_v05_tasks
Revises: 0005_v03_keyword_retrieval
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_v05_tasks"
down_revision: str | None = "0005_v03_keyword_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_tasks_tenant_id", "processing_tasks", ["tenant_id"])
    op.create_index("ix_processing_tasks_knowledge_base_id", "processing_tasks", ["knowledge_base_id"])
    op.create_index("ix_processing_tasks_document_id", "processing_tasks", ["document_id"])
    op.create_index("ix_processing_tasks_task_type", "processing_tasks", ["task_type"])
    op.create_index("ix_processing_tasks_status", "processing_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_processing_tasks_status", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_task_type", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_document_id", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_knowledge_base_id", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_tenant_id", table_name="processing_tasks")
    op.drop_table("processing_tasks")
