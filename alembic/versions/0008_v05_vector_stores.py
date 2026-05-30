"""add v0.5 vector stores

Revision ID: 0008_v05_vector_stores
Revises: 0007_v05_faq_kb_type
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_v05_vector_stores"
down_revision: str | None = "0007_v05_faq_kb_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vector_stores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vector_stores_tenant_id", "vector_stores", ["tenant_id"])
    op.create_index("ix_vector_stores_provider", "vector_stores", ["provider"])
    op.create_index("ix_vector_stores_status", "vector_stores", ["status"])
    op.create_index("ix_vector_stores_is_default", "vector_stores", ["is_default"])


def downgrade() -> None:
    op.drop_index("ix_vector_stores_is_default", table_name="vector_stores")
    op.drop_index("ix_vector_stores_status", table_name="vector_stores")
    op.drop_index("ix_vector_stores_provider", table_name="vector_stores")
    op.drop_index("ix_vector_stores_tenant_id", table_name="vector_stores")
    op.drop_table("vector_stores")
