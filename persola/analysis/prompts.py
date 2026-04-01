from __future__ import annotations

from ..models import KNOB_DEFINITIONS


ANALYSIS_PROMPT_INTRO = """You are analyzing a writing sample to infer the author's communication and reasoning style.
Return only valid JSON. Do not include markdown, explanations, or code fences.

Score each knob on a 0.0 to 1.0 scale where:
- 0.0 means the trait is minimally present
- 0.5 means balanced or unclear
- 1.0 means the trait is strongly present

Use the text as evidence. If a trait is ambiguous, keep it near 0.5.
Do not infer personal identity, demographic traits, or private facts.
"""


def build_analysis_prompt(text: str) -> str:
    knob_lines = "\n".join(
        f'- "{knob.key}": {knob.description}'
        for knob in KNOB_DEFINITIONS
    )
    return (
        f"{ANALYSIS_PROMPT_INTRO}\n"
        "Return a JSON object with this shape:\n"
        "{\n"
        '  "analysis": {\n'
        f"{knob_lines}\n"
        "  },\n"
        '  "confidence_score": 0.0,\n'
        '  "notes": "short summary of the detected style"\n'
        "}\n\n"
        "Writing sample:\n"
        '"""\n'
        f"{text.strip()}\n"
        '"""'
    )