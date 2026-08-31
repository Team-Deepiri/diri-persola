"""workqueue persistence — org chart, tasks, audit trail

Revision ID: 006_workqueue
Revises: 005_city_life_cycle
Create Date: 2026-08-16 12:00:00
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_workqueue"
down_revision: Union[str, None] = "005_city_life_cycle"


def upgrade() -> None:
	op.create_table(
		"org_nodes",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("team_id", sa.String(length=100), nullable=False, server_default=sa.text("'default'")),
		sa.Column("role", sa.String(length=100), nullable=False),
		sa.Column("title", sa.String(length=255), nullable=False),
		sa.Column("reports_to", sa.String(length=100), nullable=True),
		sa.Column("email", sa.String(length=255), nullable=True),
		sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.UniqueConstraint("team_id", "role", name="uq_org_node_team_role"),
	)
	op.create_index("idx_org_nodes_team_id", "org_nodes", ["team_id"])
	op.create_table(
		"work_tasks",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("task_id", sa.String(length=100), nullable=False),
		sa.Column("team_id", sa.String(length=100), nullable=False, server_default=sa.text("'default'")),
		sa.Column("role", sa.String(length=100), nullable=False, server_default=sa.text("'coordinator'")),
		sa.Column("subtask", sa.Text(), nullable=False),
		sa.Column("origin", sa.String(length=100), nullable=False, server_default=sa.text("'user'")),
		sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'queued'")),
		sa.Column("result", sa.Text(), nullable=True),
		sa.Column("error", sa.Text(), nullable=True),
		sa.Column("parent_task_id", sa.String(length=100), nullable=True),
		sa.Column("session_id", sa.String(length=100), nullable=True),
		sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
		sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
		sa.UniqueConstraint("task_id", name="uq_work_tasks_task_id"),
	)
	op.create_index("idx_work_tasks_team_id", "work_tasks", ["team_id"])
	op.create_index("idx_work_tasks_status", "work_tasks", ["status"])
	op.create_index("idx_work_tasks_role", "work_tasks", ["role"])
	op.create_index("idx_work_tasks_created_at", "work_tasks", ["created_at"])
	op.create_check_constraint(
		"ck_work_tasks_status",
		"work_tasks",
		"status IN ('queued', 'claimed', 'in_progress', 'blocked', 'done', 'failed')",
	)
	op.create_table(
		"audit_events",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
		sa.Column("event_id", sa.String(length=100), nullable=False),
		sa.Column("team_id", sa.String(length=100), nullable=False, server_default=sa.text("'default'")),
		sa.Column("session_id", sa.String(length=100), nullable=True),
		sa.Column("task_id", sa.String(length=100), nullable=True),
		sa.Column("event_type", sa.String(length=30), nullable=False, server_default=sa.text("'instruction'")),
		sa.Column("actor", sa.String(length=100), nullable=False, server_default=sa.text("'system'")),
		sa.Column("recipient", sa.String(length=100), nullable=True),
		sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
		sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.UniqueConstraint("event_id", name="uq_audit_events_event_id"),
	)
	op.create_index("idx_audit_events_team_id", "audit_events", ["team_id"])
	op.create_index("idx_audit_events_session_id", "audit_events", ["session_id"])
	op.create_index("idx_audit_events_task_id", "audit_events", ["task_id"])
	op.create_index("idx_audit_events_created_at", "audit_events", ["created_at"])
	op.create_check_constraint(
		"ck_audit_events_type",
		"audit_events",
		"event_type IN ('instruction', 'decision', 'reply', 'status_change', 'tool_call')",
	)


def downgrade() -> None:
	op.drop_index("idx_audit_events_created_at", table_name="audit_events")
	op.drop_index("idx_audit_events_task_id", table_name="audit_events")
	op.drop_index("idx_audit_events_session_id", table_name="audit_events")
	op.drop_index("idx_audit_events_team_id", table_name="audit_events")
	op.drop_constraint("uq_audit_events_event_id", "audit_events", type_="unique")
	op.drop_constraint("ck_audit_events_type", "audit_events", type_="check")
	op.drop_table("audit_events")
	op.drop_constraint("uq_work_tasks_task_id", "work_tasks", type_="unique")
	op.drop_constraint("ck_work_tasks_status", "work_tasks", type_="check")
	op.drop_index("idx_work_tasks_created_at", table_name="work_tasks")
	op.drop_index("idx_work_tasks_role", table_name="work_tasks")
	op.drop_index("idx_work_tasks_status", table_name="work_tasks")
	op.drop_index("idx_work_tasks_team_id", table_name="work_tasks")
	op.drop_table("work_tasks")
	op.drop_constraint("uq_org_node_team_role", "org_nodes", type_="unique")
	op.drop_index("idx_org_nodes_team_id", table_name="org_nodes")
	op.drop_table("org_nodes")
