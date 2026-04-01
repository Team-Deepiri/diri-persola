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


ANALYSIS_RETRY_PROMPT_INTRO = """Your previous response was not valid JSON.
Retry and return only a single valid JSON object.
Do not add prose, comments, markdown fences, or trailing text.
Every knob value must be a number between 0.0 and 1.0.
"""


def _build_expected_shape() -> str:
    knob_lines = "\n".join(
        f'- "{knob.key}": {knob.description}'
        for knob in KNOB_DEFINITIONS
    )
    return (
        "Return a JSON object with this shape:\n"
        "{\n"
        '  "analysis": {\n'
        f"{knob_lines}\n"
        "  },\n"
        '  "confidence_score": 0.0,\n'
        '  "notes": "short summary of the detected style"\n'
        "}"
    )


def build_analysis_prompt(text: str) -> str:
    return (
        f"{ANALYSIS_PROMPT_INTRO}\n"
        f"{_build_expected_shape()}\n\n"
        "Writing sample:\n"
        '"""\n'
        f"{text.strip()}\n"
        '"""'
    )


def build_analysis_retry_prompt(text: str, invalid_response: str) -> str:
    return (
        f"{ANALYSIS_RETRY_PROMPT_INTRO}\n"
        f"{_build_expected_shape()}\n\n"
        "Writing sample:\n"
        '"""\n'
        f"{text.strip()}\n"
        '"""\n\n'
        "Previous invalid response:\n"
        '"""\n'
        f"{invalid_response.strip()}\n"
        '"""'
    )