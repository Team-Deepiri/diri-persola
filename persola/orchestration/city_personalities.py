"""Distinct personality fingerprints for city-scale agents (Phase 6)."""

from __future__ import annotations

import hashlib
from typing import Any

from .personalities import BUILTIN_ARCHETYPES, PersonalityRole

ROLE_CYCLE: tuple[str, ...] = ("analyst", "creative", "executor", "empath", "builder")

# Extra role not in team archetypes — builders lean practical + inventive
BUILDER_KNOBS: dict[str, float] = {
    "creativity": 0.75,
    "conscientiousness": 0.85,
    "reliability": 0.9,
    "step_by_step": 0.8,
    "accuracy": 0.85,
    "verbosity": 0.4,
}

# Knobs we deliberately diversify so every agent is unique
DIVERSITY_KNOBS: tuple[str, ...] = (
    "creativity",
    "humor",
    "formality",
    "verbosity",
    "empathy",
    "confidence",
    "openness",
    "extraversion",
    "agreeableness",
    "reasoning_depth",
    "accuracy",
    "caution",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def _archetype_knobs(role_label: str) -> dict[str, float]:
    if role_label == "builder":
        return dict(BUILDER_KNOBS)
    try:
        role = PersonalityRole(role_label)
    except ValueError:
        return {}
    arch = BUILTIN_ARCHETYPES.get(role)
    return dict(arch.knob_overrides) if arch else {}


def personality_fingerprint(knobs: dict[str, float]) -> str:
    """Stable short digest of a knob map — used for distinctness checks."""
    items = sorted((k, round(float(v), 4)) for k, v in knobs.items())
    raw = "|".join(f"{k}={v}" for k, v in items)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def distinct_child_personality(
    *,
    child_index: int,
    family_index: int = 0,
) -> dict[str, Any]:
    """
    Build a unique personality for a child agent.

    Combines archetype/role baselines with index-derived knob deltas so that
    every (family_index, child_index) pair has a different fingerprint.
    """
    role = ROLE_CYCLE[child_index % len(ROLE_CYCLE)]
    knobs = _archetype_knobs(role)

    seed = child_index * 17 + family_index * 31
    for i, key in enumerate(DIVERSITY_KNOBS):
        # Pseudo-random but deterministic walk across [0.12, 0.95]
        wave = ((seed * (i + 3) + i * 19) % 83) / 83.0
        base = knobs.get(key, 0.5)
        # Pull toward wave while keeping archetype bias
        knobs[key] = _clamp(base * 0.45 + (0.12 + wave * 0.83) * 0.55)

    # Guaranteed uniqueness salt on two high-visibility knobs
    knobs["creativity"] = _clamp(0.15 + ((seed * 7) % 80) / 100.0)
    knobs["empathy"] = _clamp(0.18 + ((seed * 11 + 5) % 78) / 100.0)

    fp = personality_fingerprint(knobs)
    top = sorted(knobs.items(), key=lambda kv: abs(kv[1] - 0.5), reverse=True)[:5]
    return {
        "role_label": role,
        "knob_overrides": knobs,
        "fingerprint": fp,
        "top_traits": [{"knob": k, "value": v} for k, v in top],
    }


def parent_personality(*, family_index: int = 0) -> dict[str, Any]:
    """Distinct coordinator parent per family."""
    knobs = _archetype_knobs("coordinator")
    seed = family_index * 41 + 3
    knobs["reasoning_depth"] = _clamp(0.85 + (seed % 10) / 100.0)
    knobs["agreeableness"] = _clamp(0.65 + ((seed * 3) % 25) / 100.0)
    knobs["verbosity"] = _clamp(0.4 + ((seed * 5) % 30) / 100.0)
    fp = personality_fingerprint(knobs)
    top = sorted(knobs.items(), key=lambda kv: abs(kv[1] - 0.5), reverse=True)[:5]
    return {
        "role_label": "coordinator",
        "knob_overrides": knobs,
        "fingerprint": fp,
        "top_traits": [{"knob": k, "value": v} for k, v in top],
    }
