"""multi-tenant scoping

Revision ID: 004_multi_tenancy
Revises: 003_team_orchestration
Create Date: 2026-09-01 00:00:00

Adds a tenant_id column to every user-scoped table. Existing rows are
assigned the DEFAULT_TENANT sentinel (all-zero UUID) so pre-tenant data is
owned by the "system"/default tenant and continues to work unchanged.

Global unique constraints on session identifiers and names are replaced with
per-tenant composite uniques so the same identifier can be reused across
different tenants.
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_multi_tenancy"
down_revision: Union[str, None] = "003_team_orchestration"

DEFAULT_TENANT = "00000000-0000-0000-0000-000000000000"

TENANT_TABLES: tuple[str, ...] = (
    "personas",
    "agents",
    "sessions",
    "messages",
    "agent_runs",
    "analysis_runs",
    "team_sessions",
    "team_workflows",
    "team_memory",
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

    # Per-tenant uniqueness for session identifiers (replaces global uniqueness).
    op.drop_constraint("sessions_session_id_key", "sessions", type_="unique")
    op.create_unique_constraint(
        "uq_sessions_tenant_session_id", "sessions", ["tenant_id", "session_id"]
    )

    op.drop_constraint(
        "team_sessions_external_session_id_key", "team_sessions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_team_sessions_tenant_external_id",
        "team_sessions",
        ["tenant_id", "external_session_id"],
    )

    # Per-tenant name uniqueness for personas and agents.
    op.create_unique_constraint("uq_personas_tenant_name", "personas", ["tenant_id", "name"])
    op.create_unique_constraint("uq_agents_tenant_name", "agents", ["tenant_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_personas_tenant_name", "personas", type_="unique")
    op.drop_constraint("uq_agents_tenant_name", "agents", type_="unique")

    op.drop_constraint("uq_team_sessions_tenant_external_id", "team_sessions", type_="unique")
    op.create_unique_constraint(
        "team_sessions_external_session_id_key", "team_sessions", ["external_session_id"]
    )

    op.drop_constraint("uq_sessions_tenant_session_id", "sessions", type_="unique")
    op.create_unique_constraint("sessions_session_id_key", "sessions", ["session_id"])

    for table in reversed(TENANT_TABLES):
        op.drop_index(f"idx_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")