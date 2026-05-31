"""add v0.6 chat sessions

Revision ID: 0009_v06_chat_sessions
Revises: 0008_v05_vector_stores
Create Date: 2026-05-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_v06_chat_sessions"
down_revision: str | None = "0008_v05_vector_stores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_tenant_id", "chat_sessions", ["tenant_id"])
    op.create_index("ix_chat_sessions_knowledge_base_id", "chat_sessions", ["knowledge_base_id"])
    op.create_index("ix_chat_sessions_last_message_at", "chat_sessions", ["last_message_at"])
    op.create_index(
        "ix_chat_sessions_tenant_pinned_last",
        "chat_sessions",
        ["tenant_id", "is_pinned", "last_message_at"],
    )
    op.create_index("ix_chat_sessions_tenant_last", "chat_sessions", ["tenant_id", "last_message_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=True),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("sources_json", sa.JSON(), nullable=True),
        sa.Column("retrieval_trace_json", sa.JSON(), nullable=True),
        sa.Column("model_config_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_tenant_id", "chat_messages", ["tenant_id"])
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_role", "chat_messages", ["role"])
    op.create_index("ix_chat_messages_status", "chat_messages", ["status"])
    op.create_index(
        "ix_chat_messages_tenant_session_created",
        "chat_messages",
        ["tenant_id", "session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_tenant_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_status", table_name="chat_messages")
    op.drop_index("ix_chat_messages_role", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_tenant_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_tenant_last", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_tenant_pinned_last", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_last_message_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_knowledge_base_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_tenant_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
