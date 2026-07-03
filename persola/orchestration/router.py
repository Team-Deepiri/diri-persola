"""Route tasks to personality archetypes by keyword fit."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .personalities import BUILTIN_ARCHETYPES, PersonalityArchetype, PersonalityRole


def score_task_for_personality(task: str, archetype: PersonalityArchetype) -> float:
    text = task.lower()
    if not text.strip():
        return 0.0
    hits = sum(1 for kw in archetype.delegation_keywords if kw in text)
    base = hits / max(len(archetype.delegation_keywords), 1)
    # Role-specific baseline so coordinator always has a floor for synthesis tasks
    role_floor = {
        PersonalityRole.COORDINATOR: 0.15,
        PersonalityRole.ANALYST: 0.1,
        PersonalityRole.CREATIVE: 0.1,
        PersonalityRole.EXECUTOR: 0.1,
        PersonalityRole.EMPATH: 0.1,
    }.get(archetype.role, 0.05)
    return min(1.0, base + role_floor)


def route_task(task: str, top_k: int = 3) -> List[Tuple[PersonalityRole, float]]:
    scores: List[Tuple[PersonalityRole, float]] = []
    for role, archetype in BUILTIN_ARCHETYPES.items():
        if role == PersonalityRole.COORDINATOR:
            continue
        scores.append((role, score_task_for_personality(task, archetype)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def select_delegation_plan(task: str) -> Dict[str, object]:
    ranked = route_task(task, top_k=3)
    specialists = [role.value for role, score in ranked if score > 0.12]
    if not specialists:
        specialists = [PersonalityRole.ANALYST.value, PersonalityRole.EXECUTOR.value]
    return {
        "coordinator": PersonalityRole.COORDINATOR.value,
        "specialists": specialists,
        "scores": {role.value: round(score, 3) for role, score in ranked},
    }
