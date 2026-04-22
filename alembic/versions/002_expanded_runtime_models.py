"""expanded runtime models

Revision ID: 002_expanded_runtime_models
Revises: 001_initial_schema
Create Date: 2026-04-01 00:00:00
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "002_expanded_runtime_models"
down_revision: Union[str, None] = "001_initial_schema"


def upgrade() -> None:
	op.add_column("personas", sa.Column("system_prompt", sa.Text(), nullable=True))

	op.create_table(
		"persona_versions",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("version_number", sa.Integer(), nullable=False),
		sa.Column("source", sa.String(length=50), nullable=False, server_default=sa.text("'manual'")),
		sa.Column("summary", sa.Text(), nullable=True),
		sa.Column("knob_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("settings_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
		sa.UniqueConstraint("persona_id", "version_number", name="uq_persona_version_number"),
	)

	op.create_table(
		"agent_tools",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("name", sa.String(length=100), nullable=False),
		sa.Column("description", sa.Text(), nullable=True),
		sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
		sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
		sa.UniqueConstraint("agent_id", "name", name="uq_agent_tool_name"),
	)

	op.create_table(
		"analysis_runs",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("source_text", sa.Text(), nullable=False),
		sa.Column("knobs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
		sa.Column("notes", sa.Text(), nullable=True),
		sa.Column("provider", sa.String(length=50), nullable=True),
		sa.Column("model", sa.String(length=100), nullable=True),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
	)

	op.create_table(
		"agent_runs",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
		sa.Column("provider", sa.String(length=50), nullable=True),
		sa.Column("model", sa.String(length=100), nullable=True),
		sa.Column("request_message", sa.Text(), nullable=False),
		sa.Column("response_message", sa.Text(), nullable=True),
		sa.Column("tokens_used", sa.Integer(), nullable=True),
		sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("completed_at", sa.TIMESTAMP(timezone=False), nullable=True),
		sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
	)

	op.create_index("idx_persona_versions_persona_id", "persona_versions", ["persona_id"])
	op.create_index("idx_agent_tools_agent_id", "agent_tools", ["agent_id"])
	op.create_index("idx_analysis_runs_persona_id", "analysis_runs", ["persona_id"])
	op.create_index("idx_analysis_runs_created_at", "analysis_runs", ["created_at"])
	op.create_index("idx_agent_runs_agent_id", "agent_runs", ["agent_id"])
	op.create_index("idx_agent_runs_session_id", "agent_runs", ["session_id"])
	op.create_index("idx_agent_runs_created_at", "agent_runs", ["created_at"])


def downgrade() -> None:
	op.drop_column("personas", "system_prompt")

	op.drop_index("idx_agent_runs_created_at", table_name="agent_runs")
	op.drop_index("idx_agent_runs_session_id", table_name="agent_runs")
	op.drop_index("idx_agent_runs_agent_id", table_name="agent_runs")
	op.drop_index("idx_analysis_runs_created_at", table_name="analysis_runs")
	op.drop_index("idx_analysis_runs_persona_id", table_name="analysis_runs")
	op.drop_index("idx_agent_tools_agent_id", table_name="agent_tools")
	op.drop_index("idx_persona_versions_persona_id", table_name="persona_versions")

	op.drop_table("agent_runs")
	op.drop_table("analysis_runs")
	op.drop_table("agent_tools")
	op.drop_table("persona_versions")
