"""task031 faq import results

Revision ID: 0015_task031_faq_import_results
Revises: 0014_task027_rendered_context
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_task031_faq_import_results"
down_revision: str | None = "0014_task027_rendered_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "faq_import_results",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("failures_json", sa.JSON(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("import_mode", sa.String(length=16), nullable=False),
        sa.Column("display_status", sa.String(length=16), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_faq_import_results_tenant_id", "faq_import_results", ["tenant_id"])
    op.create_index("ix_faq_import_results_knowledge_base_id", "faq_import_results", ["knowledge_base_id"])
    op.create_index("ix_faq_import_results_status", "faq_import_results", ["status"])
    op.create_index("ix_faq_import_results_display_status", "faq_import_results", ["display_status"])
    op.create_index(
        "ix_faq_import_results_tenant_kb_created",
        "faq_import_results",
        ["tenant_id", "knowledge_base_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_faq_import_results_tenant_kb_created", table_name="faq_import_results")
    op.drop_index("ix_faq_import_results_display_status", table_name="faq_import_results")
    op.drop_index("ix_faq_import_results_status", table_name="faq_import_results")
    op.drop_index("ix_faq_import_results_knowledge_base_id", table_name="faq_import_results")
    op.drop_index("ix_faq_import_results_tenant_id", table_name="faq_import_results")
    op.drop_table("faq_import_results")
