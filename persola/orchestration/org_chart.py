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
from typing import Dict, List, Optional

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


def _default_nodes() -> Dict[str, OrgNode]:
    """Coordinator at the top, every built-in archetype reports to it.

    This is the same shape Alook ships by default: one lead role, everyone
    else reporting up to it, so a task dropped on the coordinator fans out
    automatically.
    """
    nodes: Dict[str, OrgNode] = {}
    for role, archetype in BUILTIN_ARCHETYPES.items():
        nodes[role.value] = OrgNode(
            role=role.value,
            title=archetype.name,
            reports_to=None if role == PersonalityRole.COORDINATOR else PersonalityRole.COORDINATOR.value,
            email=f"{role.value}@team.persola.local",
        )
    return nodes


class OrgChart:
    """A team's reporting structure, keyed by ``team_id``."""

    def __init__(self) -> None:
        self._charts: Dict[str, Dict[str, OrgNode]] = {}

    def _chart(self, team_id: str) -> Dict[str, OrgNode]:
        if team_id not in self._charts:
            self._charts[team_id] = _default_nodes()
        return self._charts[team_id]

    def get(self, team_id: str) -> List[OrgNode]:
        return list(self._chart(team_id).values())

    def upsert_node(self, team_id: str, node: OrgNode) -> OrgNode:
        self._chart(team_id)[node.role] = node
        return node

    def deactivate(self, team_id: str, role: str) -> None:
        chart = self._chart(team_id)
        if role in chart:
            chart[role].active = False

    def manager_of(self, team_id: str, role: str) -> Optional[OrgNode]:
        chart = self._chart(team_id)
        node = chart.get(role)
        if node is None or node.reports_to is None:
            return None
        return chart.get(node.reports_to)

    def reports_of(self, team_id: str, role: str) -> List[OrgNode]:
        chart = self._chart(team_id)
        return [n for n in chart.values() if n.reports_to == role and n.active]

    def top_of_chart(self, team_id: str) -> Optional[OrgNode]:
        chart = self._chart(team_id)
        for node in chart.values():
            if node.reports_to is None and node.active:
                return node
        return None

    def resolve_chain(self, team_id: str, role: str) -> List[str]:
        """Return the reporting chain from ``role`` up to the top, inclusive."""
        chart = self._chart(team_id)
        chain = [role]
        current = chart.get(role)
        seen = {role}
        while current and current.reports_to and current.reports_to not in seen:
            chain.append(current.reports_to)
            seen.add(current.reports_to)
            current = chart.get(current.reports_to)
        return chain

    def to_dict(self, team_id: str) -> Dict[str, object]:
        chart = self._chart(team_id)
        return {
            "team_id": team_id,
            "top": self.top_of_chart(team_id).role if self.top_of_chart(team_id) else None,
            "nodes": [n.to_dict() for n in chart.values()],
        }


# Process-wide org chart store, same pattern as GLOBAL_MEMORY.
GLOBAL_ORG_CHART = OrgChart()
