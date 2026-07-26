"""Phase 7 — district work templates and personality routing for city pulse."""

from __future__ import annotations

from typing import Any

# Preferred roles to execute work in each district (first match wins)
DISTRICT_ROLE_PREFERENCE: dict[str, tuple[str, ...]] = {
	"build": ("executor", "builder", "coordinator"),
	"viz": ("creative", "empath", "builder"),
	"research": ("analyst", "coordinator", "creative"),
	"ops": ("executor", "coordinator", "builder"),
}


def pick_agent_for_district(members: list[dict[str, Any]], district: str) -> dict[str, Any] | None:
	"""Pick a family member whose role best matches the district."""
	prefs = DISTRICT_ROLE_PREFERENCE.get(district, ("executor", "coordinator"))
	by_role = {m.get("role_label"): m for m in members if m.get("role_label")}
	for role in prefs:
		if role in by_role:
			return by_role[role]
	# Fall back: any child, then parent
	child = next((m for m in members if m.get("role_in_family") == "child"), None)
	if child:
		return child
	return members[0] if members else None


def district_tool_calls(district: str, *, family_slug: str) -> list[dict[str, Any]]:
	"""Structured tool calls a family runs during a city pulse for its district."""
	d = (district or "build").lower()
	slug = family_slug.replace(" ", "-").lower()[:32] or "family"

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
	# build (default)
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
