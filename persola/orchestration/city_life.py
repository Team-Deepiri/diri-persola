"""Phase 7/8 — ecosystem life: goals, dreams, age, growth, death, succession."""

from __future__ import annotations

from typing import Any

# Demo-friendly lifespan so a few heartbeat/life ticks show generations.
DEFAULT_MAX_AGE_TICKS = 6

ROLE_GOALS: dict[str, list[str]] = {
    "coordinator": ["keep the family cohesive", "ship the district goal"],
    "analyst": ["find patterns in the commons", "reduce wasted work"],
    "creative": ["make artifacts that inspire", "spark sibling ideas"],
    "executor": ["finish the runnable piece", "keep the build green"],
    "empath": ["sense friction early", "mend cohesion gaps"],
    "builder": ["grow durable tools", "leave clear handoffs"],
}

ROLE_DREAMS: dict[str, list[str]] = {
    "coordinator": ["a city that outlives any one mind"],
    "analyst": ["truth that compounds across generations"],
    "creative": ["beauty that siblings remix forever"],
    "executor": ["zero lost knowledge when someone falls"],
    "empath": ["grief that becomes wisdom, not silence"],
    "builder": ["scaffolding the next generation climbs"],
}


def default_goals(role_label: str | None) -> list[str]:
    key = (role_label or "builder").lower()
    return list(ROLE_GOALS.get(key, ROLE_GOALS["builder"]))


def default_dreams(role_label: str | None) -> list[str]:
    key = (role_label or "builder").lower()
    return list(ROLE_DREAMS.get(key, ROLE_DREAMS["builder"]))


def default_structured_thinking(role_label: str | None) -> float:
    key = (role_label or "").lower()
    if key in {"analyst", "coordinator"}:
        return 0.72
    if key in {"executor", "builder"}:
        return 0.58
    if key == "creative":
        return 0.48
    return 0.55


def living_members(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter serialized members to living, active agents."""
    out: list[dict[str, Any]] = []
    for m in members:
        status = (m.get("life_status") or "alive").lower()
        if status == "deceased":
            continue
        if m.get("is_active") is False:
            continue
        out.append(m)
    return out


def mutate_knobs(knobs: dict[str, float], *, generation: int) -> dict[str, float]:
    """Slight personality drift each generation — identity persists, traits evolve."""
    out: dict[str, float] = {}
    salt = (generation * 17) % 11
    for i, (k, v) in enumerate(knobs.items()):
        delta = ((salt + i) % 5 - 2) * 0.03
        nv = float(v) + delta
        out[k] = max(0.0, min(1.0, nv))
    return out


def inherit_legacy(member: dict[str, Any]) -> dict[str, Any]:
    """Bundle passed to the next generation on death."""
    return {
        "from_member_id": member.get("id"),
        "from_agent_id": member.get("agent_id"),
        "generation": member.get("generation", 0),
        "role_label": member.get("role_label"),
        "goals": list(member.get("goals") or []),
        "dreams": list(member.get("dreams") or []),
        "structured_thinking": member.get("structured_thinking", 0.5),
        "growth": member.get("growth", 0.0),
        "knob_overrides": dict(member.get("knob_overrides") or {}),
        "tool_tags": list(member.get("tool_tags") or []),
        "personality": member.get("personality"),
    }


def ecosystem_cohesion(members: list[dict[str, Any]]) -> float:
    """
    Personality-aligned cohesion for living members.

    Blends shared goals overlap, mean structured_thinking, and growth.
    """
    alive = living_members(members)
    if not alive:
        return 0.0
    goal_sets = [set(m.get("goals") or []) for m in alive]
    if len(goal_sets) >= 2:
        shared = set.intersection(*goal_sets) if goal_sets else set()
        union = set.union(*goal_sets) if goal_sets else set()
        overlap = len(shared) / max(1, len(union))
    else:
        overlap = 0.6
    thinking = sum(float(m.get("structured_thinking") or 0.5) for m in alive) / len(alive)
    growth = sum(float(m.get("growth") or 0.0) for m in alive) / len(alive)
    return round(min(1.0, 0.35 * overlap + 0.4 * thinking + 0.25 * growth + 0.15), 4)
