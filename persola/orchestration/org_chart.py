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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories.workqueue_repository import OrgNodeRepository
from ._session_store import SessionFactoryMixin
from .personalities import BUILTIN_ARCHETYPES, PersonalityRole


@dataclass
class OrgNode:
    role: str  # PersonalityRole value, or a custom role key for future personas
    title: str
    reports_to: Optional[str] = None  # role key of manager, None = top of chart
    email: Optional[str] = None  # optional agent inbox, mirrors Alook's @agent addresses
    active: bool = True

    def to_dict(self) -> Dict[str, object]:
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
    """A team's reporting structure, keyed by ``team_id``, stored in ``org_nodes``."""

    async def _ensure_seeded(self, team_id: str, session: AsyncSession) -> None:
        """Upsert missing default roles without overwriting user customization."""
        repo = OrgNodeRepository(session)
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
        self, team_id: str, session: AsyncSession
    ) -> List[OrgNode]:
        await self._ensure_seeded(team_id, session)
        repo = OrgNodeRepository(session)
        return [_hydrate_node(row) for row in await repo.list_for_team(team_id)]

    async def get(
        self, team_id: str, *, session: Optional[AsyncSession] = None
    ) -> List[OrgNode]:
        async def _op(s: AsyncSession) -> List[OrgNode]:
            return await self._nodes(team_id, s)

        return await self._run(session, _op, commit=True)

    async def upsert_node(
        self, team_id: str, node: OrgNode, *, session: Optional[AsyncSession] = None
    ) -> OrgNode:
        async def _op(s: AsyncSession) -> OrgNode:
            repo = OrgNodeRepository(s)
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
        self, team_id: str, role: str, *, session: Optional[AsyncSession] = None
    ) -> None:
        async def _op(s: AsyncSession) -> None:
            repo = OrgNodeRepository(s)
            await repo.deactivate(team_id, role)

        await self._run(session, _op, commit=True)

    async def manager_of(
        self, team_id: str, role: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[OrgNode]:
        async def _op(s: AsyncSession) -> Optional[OrgNode]:
            chart = {node.role: node for node in await self._nodes(team_id, s)}
            node = chart.get(role)
            if node is None or node.reports_to is None:
                return None
            return chart.get(node.reports_to)

        return await self._run(session, _op, commit=True)

    async def reports_of(
        self, team_id: str, role: str, *, session: Optional[AsyncSession] = None
    ) -> List[OrgNode]:
        async def _op(s: AsyncSession) -> List[OrgNode]:
            return [n for n in await self._nodes(team_id, s) if n.reports_to == role and n.active]

        return await self._run(session, _op, commit=True)

    async def top_of_chart(
        self, team_id: str, *, session: Optional[AsyncSession] = None
    ) -> Optional[OrgNode]:
        async def _op(s: AsyncSession) -> Optional[OrgNode]:
            for node in await self._nodes(team_id, s):
                if node.reports_to is None and node.active:
                    return node
            return None

        return await self._run(session, _op, commit=True)

    async def resolve_chain(
        self, team_id: str, role: str, *, session: Optional[AsyncSession] = None
    ) -> List[str]:
        """Return the reporting chain from ``role`` up to the top, inclusive."""
        async def _op(s: AsyncSession) -> List[str]:
            chart = {node.role: node for node in await self._nodes(team_id, s)}
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
        self, team_id: str, *, session: Optional[AsyncSession] = None
    ) -> Dict[str, object]:
        async def _op(s: AsyncSession) -> Dict[str, object]:
            nodes = await self._nodes(team_id, s)
            top = next((n for n in nodes if n.reports_to is None and n.active), None)
            return {
                "team_id": team_id,
                "top": top.role if top else None,
                "nodes": [n.to_dict() for n in nodes],
            }

        return await self._run(session, _op, commit=True)


# Process-wide org chart store, same pattern as GLOBAL_MEMORY.
GLOBAL_ORG_CHART = OrgChart()
