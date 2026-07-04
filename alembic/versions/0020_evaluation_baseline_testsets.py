"""evaluation baseline testsets

Revision ID: 0020_eval_baseline_sets
Revises: 0019_v10_ragas_evaluations
Create Date: 2026-07-03 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_eval_baseline_sets"
down_revision: str | None = "0019_v10_ragas_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_testsets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "knowledge_base_id", "name", name="uq_evaluation_testsets_tenant_kb_name"),
    )
    op.create_index("ix_evaluation_testsets_knowledge_base_id", "evaluation_testsets", ["knowledge_base_id"])
    op.create_index("ix_evaluation_testsets_status", "evaluation_testsets", ["status"])
    op.create_index("ix_evaluation_testsets_tenant_id", "evaluation_testsets", ["tenant_id"])
    op.create_index(
        "ix_evaluation_testsets_tenant_kb_created",
        "evaluation_testsets",
        ["tenant_id", "knowledge_base_id", "created_at"],
    )

    op.create_table(
        "evaluation_testset_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("testset_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("expected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("expected_law_name", sa.String(length=255), nullable=True),
        sa.Column("expected_article_no", sa.String(length=64), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.ForeignKeyConstraint(["testset_id"], ["evaluation_testsets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("testset_id", "sample_index", name="uq_evaluation_testset_items_testset_index"),
    )
    op.create_index("ix_evaluation_testset_items_knowledge_base_id", "evaluation_testset_items", ["knowledge_base_id"])
    op.create_index("ix_evaluation_testset_items_tenant_id", "evaluation_testset_items", ["tenant_id"])
    op.create_index(
        "ix_evaluation_testset_items_tenant_testset",
        "evaluation_testset_items",
        ["tenant_id", "testset_id"],
    )
    op.create_index("ix_evaluation_testset_items_testset_id", "evaluation_testset_items", ["testset_id"])

    op.add_column("evaluation_runs", sa.Column("testset_id", sa.String(length=36), nullable=True))
    op.add_column(
        "evaluation_runs",
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("testset_source", sa.String(length=32), nullable=False, server_default="chunk_derived"),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("metric_version", sa.String(length=64), nullable=False, server_default="ragas_semantic_v1"),
    )
    op.add_column("evaluation_runs", sa.Column("evaluator_config_json", sa.JSON(), nullable=True))
    op.create_index("ix_evaluation_runs_testset_id", "evaluation_runs", ["testset_id"])
    op.create_index("ix_evaluation_runs_is_baseline", "evaluation_runs", ["is_baseline"])
    op.create_index(
        "ix_evaluation_runs_tenant_kb_baseline",
        "evaluation_runs",
        ["tenant_id", "knowledge_base_id", "is_baseline"],
    )
    op.create_foreign_key(
        "fk_evaluation_runs_testset_id_evaluation_testsets",
        "evaluation_runs",
        "evaluation_testsets",
        ["testset_id"],
        ["id"],
    )

    op.add_column("evaluation_samples", sa.Column("expected_chunk_ids", sa.JSON(), nullable=True))
    op.add_column("evaluation_samples", sa.Column("expected_law_name", sa.String(length=255), nullable=True))
    op.add_column("evaluation_samples", sa.Column("expected_article_no", sa.String(length=64), nullable=True))
    op.add_column("evaluation_samples", sa.Column("diagnostics_json", sa.JSON(), nullable=True))

    op.alter_column("evaluation_runs", "is_baseline", server_default=None)
    op.alter_column("evaluation_runs", "testset_source", server_default=None)
    op.alter_column("evaluation_runs", "metric_version", server_default=None)


def downgrade() -> None:
    op.drop_column("evaluation_samples", "diagnostics_json")
    op.drop_column("evaluation_samples", "expected_article_no")
    op.drop_column("evaluation_samples", "expected_law_name")
    op.drop_column("evaluation_samples", "expected_chunk_ids")

    op.drop_constraint("fk_evaluation_runs_testset_id_evaluation_testsets", "evaluation_runs", type_="foreignkey")
    op.drop_index("ix_evaluation_runs_tenant_kb_baseline", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_is_baseline", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_testset_id", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "evaluator_config_json")
    op.drop_column("evaluation_runs", "metric_version")
    op.drop_column("evaluation_runs", "testset_source")
    op.drop_column("evaluation_runs", "is_baseline")
    op.drop_column("evaluation_runs", "testset_id")

    op.drop_index("ix_evaluation_testset_items_testset_id", table_name="evaluation_testset_items")
    op.drop_index("ix_evaluation_testset_items_tenant_testset", table_name="evaluation_testset_items")
    op.drop_index("ix_evaluation_testset_items_tenant_id", table_name="evaluation_testset_items")
    op.drop_index("ix_evaluation_testset_items_knowledge_base_id", table_name="evaluation_testset_items")
    op.drop_table("evaluation_testset_items")

    op.drop_index("ix_evaluation_testsets_tenant_kb_created", table_name="evaluation_testsets")
    op.drop_index("ix_evaluation_testsets_tenant_id", table_name="evaluation_testsets")
    op.drop_index("ix_evaluation_testsets_status", table_name="evaluation_testsets")
    op.drop_index("ix_evaluation_testsets_knowledge_base_id", table_name="evaluation_testsets")
    op.drop_table("evaluation_testsets")
