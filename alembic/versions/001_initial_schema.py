"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-20 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("creativity", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("humor", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("formality", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("verbosity", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("empathy", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("openness", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("conscientiousness", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("extraversion", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("agreeableness", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("neuroticism", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("reasoning_depth", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("step_by_step", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column(
            "creativity_in_reasoning", sa.Float(), nullable=False, server_default=sa.text("0.5")
        ),
        sa.Column("synthetics", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("abstraction", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("patterns", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("accuracy", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("reliability", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("caution", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("consistency", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("self_correction", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("transparency", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("model", sa.String(length=100), nullable=False, server_default=sa.text("'llama3:8b'")),
        sa.Column("temperature", sa.Float(), nullable=False, server_default=sa.text("0.7")),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default=sa.text("2000")),
        sa.Column("is_preset", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False, server_default=sa.text("'assistant'")),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=False), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    op.create_index("idx_personas_name", "personas", ["name"])
    op.create_index("idx_personas_is_preset", "personas", ["is_preset"])
    op.create_index("idx_agents_persona_id", "agents", ["persona_id"])
    op.create_index("idx_sessions_agent_id", "sessions", ["agent_id"])
    op.create_index("idx_sessions_session_id", "sessions", ["session_id"])
    op.create_index("idx_messages_session_id", "messages", ["session_id"])
    op.create_index("idx_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_messages_created_at", table_name="messages")
    op.drop_index("idx_messages_session_id", table_name="messages")
    op.drop_index("idx_sessions_session_id", table_name="sessions")
    op.drop_index("idx_sessions_agent_id", table_name="sessions")
    op.drop_index("idx_agents_persona_id", table_name="agents")
    op.drop_index("idx_personas_is_preset", table_name="personas")
    op.drop_index("idx_personas_name", table_name="personas")

    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("agents")
    op.drop_table("personas")
