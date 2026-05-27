"""add v0.2 model management and retrieval config

Revision ID: 0004_v02_model_management
Revises: 0003_parser_chunking
Create Date: 2026-05-25
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_v02_model_management"
down_revision: str | None = "0003_parser_chunking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("retrieval_config", sa.JSON(), nullable=True))
    op.add_column("model_configs", sa.Column("type", sa.String(length=32), nullable=True))
    op.add_column("model_configs", sa.Column("source", sa.String(length=32), nullable=True))
    op.add_column("model_configs", sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("model_configs", sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
    op.create_index("ix_model_configs_type", "model_configs", ["type"])
    op.create_index("ix_model_configs_status", "model_configs", ["status"])

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, tenant_id, provider, name, base_url, api_key_encrypted, api_key_last4, "
            "chat_model, embedding_model, embedding_dimension, is_active, created_at, updated_at "
            "FROM model_configs"
        )
    ).mappings().all()
    for row in rows:
        bind.execute(
            sa.text("UPDATE model_configs SET type = 'KnowledgeQA', source = 'remote' WHERE id = :id"),
            {"id": row["id"]},
        )
        if row["embedding_model"]:
            bind.execute(
                sa.text(
                    "INSERT INTO model_configs "
                    "(id, tenant_id, type, source, provider, name, base_url, api_key_encrypted, api_key_last4, "
                    "chat_model, embedding_model, embedding_dimension, is_active, is_builtin, status, "
                    "created_at, updated_at) "
                    "VALUES "
                    "(:id, :tenant_id, 'Embedding', 'remote', :provider, :name, :base_url, "
                    ":api_key_encrypted, :api_key_last4, "
                    "'', :embedding_model, :embedding_dimension, :is_active, false, 'active', :created_at, :updated_at)"
                ),
                {
                    **dict(row),
                    "id": str(uuid.uuid4()),
                    "name": f"{row['name']} Embedding",
                },
            )

    op.execute("UPDATE model_configs SET type = 'KnowledgeQA' WHERE type IS NULL")
    op.execute("UPDATE model_configs SET source = 'remote' WHERE source IS NULL")
    op.alter_column("model_configs", "type", existing_type=sa.String(length=32), nullable=False)
    op.alter_column("model_configs", "source", existing_type=sa.String(length=32), nullable=False)


def downgrade() -> None:
    op.drop_index("ix_model_configs_status", table_name="model_configs")
    op.drop_index("ix_model_configs_type", table_name="model_configs")
    op.drop_column("model_configs", "status")
    op.drop_column("model_configs", "is_builtin")
    op.drop_column("model_configs", "source")
    op.drop_column("model_configs", "type")
    op.drop_column("tenants", "retrieval_config")
