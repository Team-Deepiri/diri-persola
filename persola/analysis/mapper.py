from __future__ import annotations

from dataclasses import asdict

from ..models import KNOB_DEFINITIONS
from .extractor import StyleAnalysis


class StyleToKnobMapper:
    """Maps StyleAnalysis into PersonaProfile-compatible knob values."""

    def __init__(self) -> None:
        self._knob_keys = tuple(knob.key for knob in KNOB_DEFINITIONS)

    def map(self, analysis: StyleAnalysis) -> dict[str, float]:
        payload = asdict(analysis)
        return {key: float(payload[key]) for key in self._knob_keys}