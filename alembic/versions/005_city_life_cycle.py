"""family member life cycle — age, goals, dreams, death, succession

Revision ID: 005_city_life_cycle
Revises: 004_communal_city
Create Date: 2026-07-26 15:00:00
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_city_life_cycle"
down_revision: Union[str, None] = "004_communal_city"


def upgrade() -> None:
	op.add_column(
		"family_members",
		sa.Column("generation", sa.Integer(), nullable=False, server_default=sa.text("0")),
	)
	op.add_column(
		"family_members",
		sa.Column("age_ticks", sa.Integer(), nullable=False, server_default=sa.text("0")),
	)
	op.add_column(
		"family_members",
		sa.Column("max_age_ticks", sa.Integer(), nullable=False, server_default=sa.text("6")),
	)
	op.add_column(
		"family_members",
		sa.Column("life_status", sa.String(length=20), nullable=False, server_default=sa.text("'alive'")),
	)
	op.add_column(
		"family_members",
		sa.Column("goals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
	)
	op.add_column(
		"family_members",
		sa.Column("dreams", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
	)
	op.add_column(
		"family_members",
		sa.Column("structured_thinking", sa.Float(), nullable=False, server_default=sa.text("0.5")),
	)
	op.add_column(
		"family_members",
		sa.Column("growth", sa.Float(), nullable=False, server_default=sa.text("0.0")),
	)
	op.add_column(
		"family_members",
		sa.Column("deceased_at", sa.TIMESTAMP(timezone=False), nullable=True),
	)
	op.add_column(
		"family_members",
		sa.Column("successor_of_id", postgresql.UUID(as_uuid=True), nullable=True),
	)
	op.add_column(
		"family_members",
		sa.Column("legacy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
	)
	op.create_foreign_key(
		"fk_family_members_successor_of_id",
		"family_members",
		"family_members",
		["successor_of_id"],
		["id"],
		ondelete="SET NULL",
	)
	op.create_check_constraint(
		"ck_family_members_life_status",
		"family_members",
		"life_status IN ('alive', 'deceased')",
	)
	op.create_index("idx_family_members_life_status", "family_members", ["life_status"])
	op.create_index("idx_family_members_generation", "family_members", ["generation"])


def downgrade() -> None:
	op.drop_index("idx_family_members_generation", table_name="family_members")
	op.drop_index("idx_family_members_life_status", table_name="family_members")
	op.drop_constraint("ck_family_members_life_status", "family_members", type_="check")
	op.drop_constraint("fk_family_members_successor_of_id", "family_members", type_="foreignkey")
	op.drop_column("family_members", "legacy")
	op.drop_column("family_members", "successor_of_id")
	op.drop_column("family_members", "deceased_at")
	op.drop_column("family_members", "growth")
	op.drop_column("family_members", "structured_thinking")
	op.drop_column("family_members", "dreams")
	op.drop_column("family_members", "goals")
	op.drop_column("family_members", "life_status")
	op.drop_column("family_members", "max_age_ticks")
	op.drop_column("family_members", "age_ticks")
	op.drop_column("family_members", "generation")
