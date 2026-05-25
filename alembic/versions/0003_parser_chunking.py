"""add parser and adaptive chunking fields

Revision ID: 0003_parser_chunking
Revises: 0002_model_configs
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_parser_chunking"
down_revision: str | None = "0002_model_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("parser_engine_rules", sa.JSON(), nullable=True))
    op.add_column("chunks", sa.Column("context_header", sa.Text(), nullable=True))
    op.add_column("chunks", sa.Column("metadata", sa.JSON(), nullable=True))
    op.add_column("chunks", sa.Column("images", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "images")
    op.drop_column("chunks", "metadata")
    op.drop_column("chunks", "context_header")
    op.drop_column("knowledge_bases", "parser_engine_rules")
