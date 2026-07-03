"""team orchestration tables

Revision ID: 003_team_orchestration
Revises: 002_expanded_runtime_models
Create Date: 2026-07-03 00:00:00
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_team_orchestration"
down_revision: Union[str, None] = "002_expanded_runtime_models"


def upgrade() -> None:
	op.create_table(
		"team_sessions",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("external_session_id", sa.String(length=100), nullable=False),
		sa.Column("name", sa.String(length=255), nullable=True),
		sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("team_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("memory_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
		sa.UniqueConstraint("external_session_id"),
	)
	op.create_index("idx_team_sessions_external_id", "team_sessions", ["external_session_id"])

	op.create_table(
		"team_workflows",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("team_session_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("goal", sa.Text(), nullable=False),
		sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
		sa.Column("delegation_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("final_response", sa.Text(), nullable=True),
		sa.Column("personalities_used", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
		sa.Column("tool_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("completed_at", sa.TIMESTAMP(timezone=False), nullable=True),
		sa.ForeignKeyConstraint(["team_session_id"], ["team_sessions.id"], ondelete="CASCADE"),
	)
	op.create_index("idx_team_workflows_session_id", "team_workflows", ["team_session_id"])
	op.create_index("idx_team_workflows_status", "team_workflows", ["status"])

	op.create_table(
		"team_workflow_steps",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("step_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
		sa.Column("role", sa.String(length=50), nullable=False),
		sa.Column("task", sa.Text(), nullable=False),
		sa.Column("output", sa.Text(), nullable=False, server_default=sa.text("''")),
		sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
		sa.Column("parallel_group", sa.String(length=50), nullable=True),
		sa.Column("duration_ms", sa.Integer(), nullable=True),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["workflow_id"], ["team_workflows.id"], ondelete="CASCADE"),
	)
	op.create_index("idx_team_workflow_steps_workflow_id", "team_workflow_steps", ["workflow_id"])

	op.create_table(
		"team_memory",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("team_session_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("memory_key", sa.String(length=255), nullable=False),
		sa.Column("value", sa.Text(), nullable=False),
		sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
		sa.Column("source_role", sa.String(length=50), nullable=True),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["team_session_id"], ["team_sessions.id"], ondelete="CASCADE"),
	)
	op.create_index("idx_team_memory_session_id", "team_memory", ["team_session_id"])
	op.create_index("idx_team_memory_key", "team_memory", ["memory_key"])


def downgrade() -> None:
	op.drop_table("team_memory")
	op.drop_table("team_workflow_steps")
	op.drop_table("team_workflows")
	op.drop_table("team_sessions")
