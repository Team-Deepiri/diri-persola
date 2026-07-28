"""communal city tables — families, commons, jobs, events

Revision ID: 004_communal_city
Revises: 003_team_orchestration
Create Date: 2026-07-26 00:00:00
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_communal_city"
down_revision: Union[str, None] = "003_team_orchestration"


def upgrade() -> None:
	op.create_table(
		"families",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("name", sa.String(length=255), nullable=False),
		sa.Column("description", sa.Text(), nullable=True),
		sa.Column("default_district", sa.String(length=30), nullable=False, server_default=sa.text("'build'")),
		sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.CheckConstraint(
			"default_district IN ('build', 'viz', 'research', 'ops')",
			name="ck_families_default_district",
		),
	)
	op.create_index("idx_families_name", "families", ["name"])

	op.create_table(
		"family_members",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("parent_member_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("role_in_family", sa.String(length=20), nullable=False, server_default=sa.text("'child'")),
		sa.Column("role_label", sa.String(length=50), nullable=True),
		sa.Column("knob_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("tool_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
		sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["parent_member_id"], ["family_members.id"], ondelete="SET NULL"),
		sa.UniqueConstraint("family_id", "agent_id", name="uq_family_member_agent"),
		sa.CheckConstraint("role_in_family IN ('parent', 'child')", name="ck_family_members_role"),
	)
	op.create_index("idx_family_members_family_id", "family_members", ["family_id"])
	op.create_index("idx_family_members_agent_id", "family_members", ["agent_id"])

	op.create_table(
		"city_jobs",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("goal", sa.Text(), nullable=False),
		sa.Column("district", sa.String(length=30), nullable=False, server_default=sa.text("'build'")),
		sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
		sa.Column("result_summary", sa.Text(), nullable=True),
		sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("team_session_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("completed_at", sa.TIMESTAMP(timezone=False), nullable=True),
		sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["team_session_id"], ["team_sessions.id"], ondelete="SET NULL"),
		sa.CheckConstraint(
			"district IN ('build', 'viz', 'research', 'ops')",
			name="ck_city_jobs_district",
		),
		sa.CheckConstraint(
			"status IN ('pending', 'planned', 'running', 'completed', 'failed')",
			name="ck_city_jobs_status",
		),
	)
	op.create_index("idx_city_jobs_family_id", "city_jobs", ["family_id"])
	op.create_index("idx_city_jobs_status", "city_jobs", ["status"])

	op.create_table(
		"workspace_artifacts",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("path", sa.String(length=512), nullable=False),
		sa.Column("content", sa.Text(), nullable=True),
		sa.Column("content_type", sa.String(length=100), nullable=False, server_default=sa.text("'text/plain'")),
		sa.Column("size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")),
		sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
		sa.Column("created_by_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["job_id"], ["city_jobs.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["created_by_agent_id"], ["agents.id"], ondelete="SET NULL"),
		sa.UniqueConstraint("job_id", "path", "version", name="uq_workspace_artifact_path_version"),
	)
	op.create_index("idx_workspace_artifacts_job_id", "workspace_artifacts", ["job_id"])
	op.create_index("idx_workspace_artifacts_family_id", "workspace_artifacts", ["family_id"])
	op.create_index("idx_workspace_artifacts_path", "workspace_artifacts", ["path"])

	op.create_table(
		"workspace_runs",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
		sa.Column("tool", sa.String(length=100), nullable=False),
		sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
		sa.Column("stdout", sa.Text(), nullable=True),
		sa.Column("stderr", sa.Text(), nullable=True),
		sa.Column("duration_ms", sa.Integer(), nullable=True),
		sa.Column("started_by_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("artifact_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.Column("completed_at", sa.TIMESTAMP(timezone=False), nullable=True),
		sa.ForeignKeyConstraint(["job_id"], ["city_jobs.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["started_by_agent_id"], ["agents.id"], ondelete="SET NULL"),
		sa.CheckConstraint(
			"status IN ('pending', 'running', 'succeeded', 'failed', 'timeout', 'denied')",
			name="ck_workspace_runs_status",
		),
	)
	op.create_index("idx_workspace_runs_job_id", "workspace_runs", ["job_id"])
	op.create_index("idx_workspace_runs_status", "workspace_runs", ["status"])

	op.create_table(
		"city_events",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
		sa.Column("event_type", sa.String(length=80), nullable=False),
		sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text("now()")),
		sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["job_id"], ["city_jobs.id"], ondelete="CASCADE"),
	)
	op.create_index("idx_city_events_job_id", "city_events", ["job_id"])
	op.create_index("idx_city_events_family_id", "city_events", ["family_id"])
	op.create_index("idx_city_events_type", "city_events", ["event_type"])
	op.create_index("idx_city_events_created_at", "city_events", ["created_at"])


def downgrade() -> None:
	op.drop_table("city_events")
	op.drop_table("workspace_runs")
	op.drop_table("workspace_artifacts")
	op.drop_table("city_jobs")
	op.drop_table("family_members")
	op.drop_table("families")
