"""add mineru parser provider configs

Revision ID: 0018_mineru_parser_configs
Revises: 0017_v09_paradedb_bm25
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_mineru_parser_configs"
down_revision: str | None = "0017_v09_paradedb_bm25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MINERU_RULES_JSON = """
[
  {
    "file_types": [
      "pdf",
      "doc",
      "docx",
      "ppt",
      "pptx",
      "xls",
      "xlsx",
      "png",
      "jpg",
      "jpeg",
      "jp2",
      "webp",
      "gif",
      "bmp"
    ],
    "engine": "mineru"
  },
  {"file_types": ["md", "markdown"], "engine": "builtin"},
  {"file_types": ["txt"], "engine": "builtin"},
  {"file_types": ["csv", "json"], "engine": "builtin"}
]
"""

LEGACY_RULES_JSON = """
[
  {"file_types": ["pdf"], "engine": "builtin"},
  {"file_types": ["docx"], "engine": "builtin"},
  {"file_types": ["md", "markdown"], "engine": "builtin"},
  {"file_types": ["txt"], "engine": "builtin"},
  {"file_types": ["csv", "json", "xlsx"], "engine": "builtin"}
]
"""


def upgrade() -> None:
    op.create_table(
        "parser_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("api_key_last4", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_parser_provider_configs_tenant_provider"),
    )
    op.create_index("ix_parser_provider_configs_tenant_id", "parser_provider_configs", ["tenant_id"])
    op.create_index("ix_parser_provider_configs_provider", "parser_provider_configs", ["provider"])
    op.create_index(
        "ix_parser_provider_configs_tenant_provider",
        "parser_provider_configs",
        ["tenant_id", "provider"],
    )
    op.create_index("ix_parser_provider_configs_status", "parser_provider_configs", ["status"])
    _set_parser_rules(MINERU_RULES_JSON)


def downgrade() -> None:
    _set_parser_rules(LEGACY_RULES_JSON)
    op.drop_index("ix_parser_provider_configs_status", table_name="parser_provider_configs")
    op.drop_index("ix_parser_provider_configs_tenant_provider", table_name="parser_provider_configs")
    op.drop_index("ix_parser_provider_configs_provider", table_name="parser_provider_configs")
    op.drop_index("ix_parser_provider_configs_tenant_id", table_name="parser_provider_configs")
    op.drop_table("parser_provider_configs")


def _set_parser_rules(rules_json: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE knowledge_bases
                SET parser_engine_rules = CAST(:rules AS json)
                WHERE deleted_at IS NULL AND COALESCE(kb_type, 'document') = 'document'
                """
            ).bindparams(rules=rules_json)
        )
    else:
        op.execute(
            sa.text(
                """
                UPDATE knowledge_bases
                SET parser_engine_rules = :rules
                WHERE deleted_at IS NULL AND COALESCE(kb_type, 'document') = 'document'
                """
            ).bindparams(rules=rules_json)
        )
