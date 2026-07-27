"""Phase 7/8 — district work templates and personality routing for city pulse."""

from __future__ import annotations

from typing import Any
from uuid import UUID

# Preferred roles to execute work in each district (first match wins)
DISTRICT_ROLE_PREFERENCE: dict[str, tuple[str, ...]] = {
	"build": ("executor", "builder", "coordinator"),
	"viz": ("creative", "empath", "builder"),
	"research": ("analyst", "coordinator", "creative"),
	"ops": ("executor", "coordinator", "builder"),
}

# Supporting roles that always leave a note during multi-contributor pulse (Phase 8)
SUPPORT_ROLES: tuple[str, ...] = ("analyst", "creative", "empath", "builder")


def pick_agent_for_district(members: list[dict[str, Any]], district: str) -> dict[str, Any] | None:
	"""Pick a living family member whose role best matches the district."""
	from .city_life import living_members

	pool = living_members(members)
	prefs = DISTRICT_ROLE_PREFERENCE.get(district, ("executor", "coordinator"))
	by_role = {m.get("role_label"): m for m in pool if m.get("role_label")}
	for role in prefs:
		if role in by_role:
			return by_role[role]
	child = next((m for m in pool if m.get("role_in_family") == "child"), None)
	if child:
		return child
	return pool[0] if pool else None


def _slug(family_slug: str) -> str:
	return family_slug.replace(" ", "-").lower()[:32] or "family"


def district_tool_calls(district: str, *, family_slug: str) -> list[dict[str, Any]]:
	"""Structured tool calls a family runs during a city pulse for its district."""
	d = (district or "build").lower()
	slug = _slug(family_slug)

	if d == "viz":
		return [
			{
				"name": "workspace_write",
				"args": {
					"path": f"viz/{slug}.json",
					"content": (
						'{"kind":"city-viz","family":"'
						+ slug
						+ '","palette":["teal","violet","amber"],"nodes":"lineage"}\n'
					),
				},
			},
			{
				"name": "emit_viz_event",
				"args": {
					"event_type": "viz.pulse",
					"payload": {"district": "viz", "family": slug, "mood": "radiant"},
				},
			},
		]
	if d == "research":
		return [
			{
				"name": "workspace_write",
				"args": {
					"path": f"research/{slug}.md",
					"content": (
						f"# Research — {slug}\n\n"
						"Findings: cohesion rises when siblings share the commons.\n"
						"Next: compare district latency under pulse load.\n"
					),
				},
			},
			{
				"name": "emit_viz_event",
				"args": {
					"event_type": "viz.pulse",
					"payload": {"district": "research", "family": slug, "mood": "curious"},
				},
			},
		]
	if d == "ops":
		return [
			{
				"name": "workspace_write",
				"args": {
					"path": f"ops/{slug}_health.py",
					"content": (
						'print("ops-ok")\n'
						f'print("family", "{slug}")\n'
						'print("checks", 3)\n'
					),
				},
			},
			{"name": "run_python", "args": {"path": f"ops/{slug}_health.py"}},
		]
	return [
		{
			"name": "workspace_write",
			"args": {
				"path": f"build/{slug}.py",
				"content": (
					'print("city-pulse-build")\n'
					f'print("family", "{slug}")\n'
					'print("sum", 2 + 2)\n'
				),
			},
		},
		{"name": "run_python", "args": {"path": f"build/{slug}.py"}},
	]


def support_note_call(role: str, *, family_slug: str, district: str) -> dict[str, Any]:
	"""One sibling contribution note for multi-contributor pulse."""
	slug = _slug(family_slug)
	return {
		"name": "workspace_write",
		"args": {
			"path": f"notes/{slug}_{role}.md",
			"content": (
				f"# {role.title()} note — {slug}\n"
				f"District: {district}\n"
				f"I contributed as {role} so the family commons stays cohesive.\n"
			),
		},
	}


def multi_contributor_plan(
	members: list[dict[str, Any]],
	*,
	district: str,
	family_slug: str,
) -> list[dict[str, Any]]:
	"""
	Phase 8 plan: support roles leave notes, then district lead executes primary tools.

	Returns a list of {agent_id, role_label, calls} batches.
	"""
	from .city_life import living_members

	pool = living_members(members)
	by_role = {m.get("role_label"): m for m in pool if m.get("role_label") and m.get("agent_id")}
	lead = pick_agent_for_district(pool, district)
	batches: list[dict[str, Any]] = []

	for role in SUPPORT_ROLES:
		member = by_role.get(role)
		if member is None:
			continue
		if lead and member.get("agent_id") == lead.get("agent_id"):
			continue
		batches.append(
			{
				"agent_id": member["agent_id"],
				"role_label": role,
				"calls": [support_note_call(role, family_slug=family_slug, district=district)],
			}
		)

	if lead and lead.get("agent_id"):
		batches.append(
			{
				"agent_id": lead["agent_id"],
				"role_label": lead.get("role_label"),
				"calls": district_tool_calls(district, family_slug=family_slug),
			}
		)
	elif pool:
		m = pool[0]
		batches.append(
			{
				"agent_id": m.get("agent_id"),
				"role_label": m.get("role_label"),
				"calls": district_tool_calls(district, family_slug=family_slug),
			}
		)

	return batches


def parse_agent_uuid(agent_id: str | None) -> UUID | None:
	if not agent_id:
		return None
	try:
		return UUID(str(agent_id))
	except (TypeError, ValueError):
		return None
