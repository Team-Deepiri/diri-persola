"""multi-tenancy for the workqueue tables

Revision ID: 007_workqueue_multi_tenancy
Revises: 006_workqueue
Create Date: 2026-09-02 00:00:00

The 004_multi_tenancy migration scoped the core entity tables but predated
the workqueue persistence (006_workqueue), so org_chart / task_queue /
audit_log tables were left un-scoped. This migration backfills them:

* adds a tenant_id column (server default = DEFAULT_TENANT sentinel) so
  pre-existing rows become system-owned, matching 004's approach.
* replaces the global unique constraints with per-tenant composite uniques.
"""


import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007_workqueue_multi_tenancy"
down_revision: str | None = "006_workqueue"

DEFAULT_TENANT = "00000000-0000-0000-0000-000000000000"

TENANT_TABLES: tuple[str, ...] = (
    "org_nodes",
    "work_tasks",
    "audit_events",
)


def upgrade() -> None:
    tenant_type = postgresql.UUID(as_uuid=True)
    default_expr = sa.text(f"'{DEFAULT_TENANT}'::uuid")

    for table in TENANT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                tenant_type,
                server_default=default_expr,
                nullable=False,
            ),
        )
        op.create_index(f"idx_{table}_tenant_id", table, ["tenant_id"])

    # Per-tenant uniqueness for org chart nodes (replaces global uniqueness).
    op.drop_constraint("uq_org_node_team_role", "org_nodes", type_="unique")
    op.create_unique_constraint(
        "uq_org_node_tenant_team_role", "org_nodes", ["tenant_id", "team_id", "role"]
    )

    # Per-tenant uniqueness for work tasks (replaces global task_id uniqueness).
    op.drop_constraint("uq_work_tasks_task_id", "work_tasks", type_="unique")
    op.create_unique_constraint(
        "uq_work_tasks_tenant_task_id", "work_tasks", ["tenant_id", "task_id"]
    )

    # Per-tenant uniqueness for audit events (replaces global event_id uniqueness).
    op.drop_constraint("uq_audit_events_event_id", "audit_events", type_="unique")
    op.create_unique_constraint(
        "uq_audit_events_tenant_event_id", "audit_events", ["tenant_id", "event_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_audit_events_tenant_event_id", "audit_events", type_="unique")
    op.create_unique_constraint("uq_audit_events_event_id", "audit_events", ["event_id"])

    op.drop_constraint("uq_work_tasks_tenant_task_id", "work_tasks", type_="unique")
    op.create_unique_constraint("uq_work_tasks_task_id", "work_tasks", ["task_id"])

    op.drop_constraint("uq_org_node_tenant_team_role", "org_nodes", type_="unique")
    op.create_unique_constraint("uq_org_node_team_role", "org_nodes", ["team_id", "role"])

    for table in reversed(TENANT_TABLES):
        op.drop_index(f"idx_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
