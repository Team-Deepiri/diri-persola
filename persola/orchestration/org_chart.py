"""Org chart — reporting lines and top-down task distribution.

Modeled on Alook's collaboration layer: a human defines an org chart
(roles + reporting lines), and a task assigned at the top is distributed
automatically without manual routing, with every hop resolvable back into
who-reports-to-whom.

Persola's ``router.select_delegation_plan`` already scores a *flat* set of
specialists for a task. This module adds the missing piece: a persistent
hierarchy so delegation can flow coordinator -> specialist -> (optional)
sub-specialist, and so the audit log / kanban board can show a real org
chart instead of an anonymous list of roles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories.workqueue_repository import OrgNodeRepository
from ._session_store import SessionFactoryMixin
from .personalities import BUILTIN_ARCHETYPES, PersonalityRole


@dataclass
class OrgNode:
    role: str  # PersonalityRole value, or a custom role key for future personas
    title: str
    reports_to: str | None = None  # role key of manager, None = top of chart
    email: str | None = None  # optional agent inbox, mirrors Alook's @agent addresses
    active: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "title": self.title,
            "reports_to": self.reports_to,
            "email": self.email,
            "active": self.active,
        }


def _hydrate_node(row: Any) -> OrgNode:
    return OrgNode(
        role=row.role,
        title=row.title,
        reports_to=row.reports_to,
        email=row.email,
        active=row.active,
    )


class OrgChart(SessionFactoryMixin):
    """A team's reporting structure, keyed by ``team_id``, stored in ``org_nodes``.

    ``tenant_id`` scopes reads/writes to a single tenant; when omitted the
    repository is unscoped (legacy behaviour).
    """

    async def _ensure_seeded(self, team_id: str, session: AsyncSession, tenant_id: UUID | None = None) -> None:
        """Upsert missing default roles without overwriting user customization."""
        repo = OrgNodeRepository(session, tenant_id=tenant_id)
        existing = {node.role for node in await repo.list_for_team(team_id)}
        for role, archetype in BUILTIN_ARCHETYPES.items():
            if role.value not in existing:
                await repo.upsert(
                    team_id,
                    role=role.value,
                    title=archetype.name,
                    reports_to=None if role == PersonalityRole.COORDINATOR else PersonalityRole.COORDINATOR.value,
                    email=f"{role.value}@team.persola.local",
                )
        await session.flush()

    async def _nodes(
        self, team_id: str, session: AsyncSession, tenant_id: UUID | None = None
    ) -> list[OrgNode]:
        await self._ensure_seeded(team_id, session, tenant_id)
        repo = OrgNodeRepository(session, tenant_id=tenant_id)
        return [_hydrate_node(row) for row in await repo.list_for_team(team_id)]

    async def get(
        self, team_id: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> list[OrgNode]:
        async def _op(s: AsyncSession) -> list[OrgNode]:
            return await self._nodes(team_id, s, tenant_id)

        return await self._run(session, _op, commit=True)

    async def upsert_node(
        self, team_id: str, node: OrgNode, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> OrgNode:
        async def _op(s: AsyncSession) -> OrgNode:
            repo = OrgNodeRepository(s, tenant_id=tenant_id)
            row = await repo.upsert(
                team_id,
                role=node.role,
                title=node.title,
                reports_to=node.reports_to,
                email=node.email,
                active=node.active,
            )
            return _hydrate_node(row)

        return await self._run(session, _op, commit=True)

    async def deactivate(
        self, team_id: str, role: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> None:
        async def _op(s: AsyncSession) -> None:
            repo = OrgNodeRepository(s, tenant_id=tenant_id)
            await repo.deactivate(team_id, role)

        await self._run(session, _op, commit=True)

    async def manager_of(
        self, team_id: str, role: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> OrgNode | None:
        async def _op(s: AsyncSession) -> OrgNode | None:
            chart = {node.role: node for node in await self._nodes(team_id, s, tenant_id)}
            node = chart.get(role)
            if node is None or node.reports_to is None:
                return None
            return chart.get(node.reports_to)

        return await self._run(session, _op, commit=True)

    async def reports_of(
        self, team_id: str, role: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> list[OrgNode]:
        async def _op(s: AsyncSession) -> list[OrgNode]:
            return [n for n in await self._nodes(team_id, s, tenant_id) if n.reports_to == role and n.active]

        return await self._run(session, _op, commit=True)

    async def top_of_chart(
        self, team_id: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> OrgNode | None:
        async def _op(s: AsyncSession) -> OrgNode | None:
            for node in await self._nodes(team_id, s, tenant_id):
                if node.reports_to is None and node.active:
                    return node
            return None

        return await self._run(session, _op, commit=True)

    async def resolve_chain(
        self, team_id: str, role: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> list[str]:
        """Return the reporting chain from ``role`` up to the top, inclusive."""
        async def _op(s: AsyncSession) -> list[str]:
            chart = {node.role: node for node in await self._nodes(team_id, s, tenant_id)}
            chain = [role]
            current = chart.get(role)
            seen = {role}
            while current and current.reports_to and current.reports_to not in seen:
                chain.append(current.reports_to)
                seen.add(current.reports_to)
                current = chart.get(current.reports_to)
            return chain

        return await self._run(session, _op, commit=True)

    async def to_dict(
        self, team_id: str, *, session: AsyncSession | None = None, tenant_id: UUID | None = None
    ) -> dict[str, object]:
        async def _op(s: AsyncSession) -> dict[str, object]:
            nodes = await self._nodes(team_id, s, tenant_id)
            top = next((n for n in nodes if n.reports_to is None and n.active), None)
            return {
                "team_id": team_id,
                "top": top.role if top else None,
                "nodes": [n.to_dict() for n in nodes],
            }

        return await self._run(session, _op, commit=True)


# Process-wide org chart store, same pattern as GLOBAL_MEMORY.
GLOBAL_ORG_CHART = OrgChart()
