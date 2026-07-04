"""v10 ragas evaluations

Revision ID: 0019_v10_ragas_evaluations
Revises: 0018_mineru_parser_configs
Create Date: 2026-06-27 23:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_v10_ragas_evaluations"
down_revision: str | None = "0018_mineru_parser_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("testset_size", sa.Integer(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=True),
        sa.Column("enable_rerank", sa.Boolean(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("completed_sample_count", sa.Integer(), nullable=False),
        sa.Column("failed_sample_count", sa.Integer(), nullable=False),
        sa.Column("metrics_summary", sa.JSON(), nullable=True),
        sa.Column("model_config_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_knowledge_base_id", "evaluation_runs", ["knowledge_base_id"])
    op.create_index("ix_evaluation_runs_tenant_id", "evaluation_runs", ["tenant_id"])
    op.create_index(
        "ix_evaluation_runs_tenant_kb_created",
        "evaluation_runs",
        ["tenant_id", "knowledge_base_id", "created_at"],
    )
    op.create_index("ix_evaluation_runs_tenant_status", "evaluation_runs", ["tenant_id", "status"])

    op.create_table(
        "evaluation_samples",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("reference_contexts", sa.JSON(), nullable=True),
        sa.Column("synthesizer_name", sa.String(length=128), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("retrieved_contexts", sa.JSON(), nullable=True),
        sa.Column("sources_json", sa.JSON(), nullable=True),
        sa.Column("retrieval_trace_json", sa.JSON(), nullable=True),
        sa.Column("scores_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_run_id", "sample_index", name="uq_evaluation_samples_run_index"),
    )
    op.create_index("ix_evaluation_samples_evaluation_run_id", "evaluation_samples", ["evaluation_run_id"])
    op.create_index("ix_evaluation_samples_kb_status", "evaluation_samples", ["knowledge_base_id", "status"])
    op.create_index("ix_evaluation_samples_knowledge_base_id", "evaluation_samples", ["knowledge_base_id"])
    op.create_index("ix_evaluation_samples_tenant_id", "evaluation_samples", ["tenant_id"])
    op.create_index("ix_evaluation_samples_tenant_run", "evaluation_samples", ["tenant_id", "evaluation_run_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_samples_tenant_run", table_name="evaluation_samples")
    op.drop_index("ix_evaluation_samples_tenant_id", table_name="evaluation_samples")
    op.drop_index("ix_evaluation_samples_knowledge_base_id", table_name="evaluation_samples")
    op.drop_index("ix_evaluation_samples_kb_status", table_name="evaluation_samples")
    op.drop_index("ix_evaluation_samples_evaluation_run_id", table_name="evaluation_samples")
    op.drop_table("evaluation_samples")
    op.drop_index("ix_evaluation_runs_tenant_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_tenant_kb_created", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_tenant_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_knowledge_base_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
