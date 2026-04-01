from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable

from ..integrations.llm import PersolaLLM, get_llm_provider
from ..models import KNOB_DEFINITIONS
from .prompts import build_analysis_prompt


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 3)))


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return float(mean(items))


@dataclass(slots=True)
class StyleAnalysis:
    formality: float = 0.5
    creativity: float = 0.5
    humor: float = 0.5
    verbosity: float = 0.5
    empathy: float = 0.5
    confidence: float = 0.5
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    reasoning_depth: float = 0.5
    step_by_step: float = 0.5
    creativity_in_reasoning: float = 0.5
    synthetics: float = 0.5
    abstraction: float = 0.5
    patterns: float = 0.5
    accuracy: float = 0.8
    reliability: float = 0.8
    caution: float = 0.5
    consistency: float = 0.8
    self_correction: float = 0.5
    transparency: float = 0.5
    confidence_score: float = 0.0
    notes: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "StyleAnalysis":
        analysis_payload = payload.get("analysis", payload)
        if not isinstance(analysis_payload, dict):
            raise TypeError("analysis payload must be a dictionary")

        defaults = cls()
        values: dict[str, object] = {
            key: analysis_payload.get(key)
            for key in cls.knob_keys()
        }
        values["confidence_score"] = payload.get("confidence_score", values.get("confidence_score", 0.0))
        values["notes"] = payload.get("notes", "")
        normalized: dict[str, object] = {}
        for key, value in values.items():
            if key == "notes":
                normalized[key] = str(value or "")
            else:
                normalized[key] = _clamp(float(value if value is not None else getattr(defaults, key)))
        return cls(**normalized)

    @classmethod
    def knob_keys(cls) -> tuple[str, ...]:
        return tuple(knob.key for knob in KNOB_DEFINITIONS)

    def to_knob_dict(self) -> dict[str, float]:
        payload = asdict(self)
        return {key: float(payload[key]) for key in self.knob_keys()}


class WritingStyleExtractor:
    """Uses an LLM to extract structured style signals from writing samples."""

    def __init__(
        self,
        provider: str = "auto",
        model: str = "llama3:8b",
        temperature: float = 0.2,
        max_tokens: int = 1200,
        llm: PersolaLLM | None = None,
    ) -> None:
        self.llm = llm or get_llm_provider(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def extract(self, text: str) -> StyleAnalysis:
        sample = text.strip()
        if not sample:
            raise ValueError("text must not be empty")

        if not self.llm.is_available():
            return self._heuristic_analysis(sample, notes_prefix="LLM unavailable; used heuristic analysis.")

        prompt = build_analysis_prompt(sample)
        response = await self.llm.generate(prompt)
        parsed = self._parse_response(response)
        if parsed is None:
            return self._heuristic_analysis(sample, notes_prefix="Could not parse structured LLM output; used heuristic analysis.")
        return parsed

    def _parse_response(self, response: str) -> StyleAnalysis | None:
        candidates = [response.strip()]
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", response, re.DOTALL)
        if fenced_match:
            candidates.insert(0, fenced_match.group(1).strip())

        json_match = re.search(r"(\{.*\})", response, re.DOTALL)
        if json_match:
            candidates.append(json_match.group(1).strip())

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            try:
                return StyleAnalysis.from_payload(payload)
            except (TypeError, ValueError):
                continue
        return None

    def _heuristic_analysis(self, text: str, notes_prefix: str) -> StyleAnalysis:
        words = re.findall(r"\b\w+\b", text)
        sentences = [segment.strip() for segment in re.split(r"[.!?]+", text) if segment.strip()]
        word_count = len(words)
        avg_word_len = _average(len(word) for word in words)
        avg_sentence_len = _average(len(re.findall(r"\b\w+\b", sentence)) for sentence in sentences)
        exclamations = text.count("!")
        questions = text.count("?")
        first_person = len(re.findall(r"\b(I|me|my|mine|we|our|ours)\b", text, re.IGNORECASE))
        hedges = len(re.findall(r"\b(maybe|perhaps|might|could|possibly|seems|appears)\b", text, re.IGNORECASE))
        structure_markers = len(re.findall(r"\b(first|second|third|next|finally|therefore|because|however)\b", text, re.IGNORECASE))
        humor_markers = len(re.findall(r"\b(haha|lol|funny|joke|sarcasm)\b", text, re.IGNORECASE))

        verbosity = _clamp(word_count / 400)
        formality = _clamp((avg_word_len - 3.5) / 4.5)
        creativity = _clamp((len(set(words)) / word_count) if word_count else 0.5)
        humor = _clamp((humor_markers + exclamations * 0.15) / 6)
        empathy = _clamp(first_person / max(word_count / 20, 1))
        confidence = _clamp(0.75 - (hedges / max(len(sentences), 1)) * 0.15)
        reasoning_depth = _clamp(avg_sentence_len / 24)
        step_by_step = _clamp(structure_markers / max(len(sentences), 1))
        creativity_in_reasoning = _clamp((creativity + structure_markers / 10) / 2)
        synthetics = _clamp((questions + structure_markers) / max(len(sentences) * 2, 1))
        abstraction = _clamp((avg_word_len - 4.0) / 4.0)
        patterns = _clamp(structure_markers / max(len(sentences), 1))
        openness = _clamp((creativity + questions / max(len(sentences), 1)) / 2)
        conscientiousness = _clamp((step_by_step + reasoning_depth) / 2)
        extraversion = _clamp((exclamations + first_person) / max(len(sentences) * 2, 1))
        agreeableness = _clamp((empathy + 0.6) / 2)
        neuroticism = _clamp((hedges + questions * 0.5) / max(len(sentences) * 2, 1))
        accuracy = _clamp((reasoning_depth + conscientiousness + 0.8) / 3)
        reliability = _clamp((conscientiousness + consistency_hint(text) + 0.8) / 3)
        caution = _clamp((hedges / max(len(sentences), 1)) + 0.2)
        consistency = _clamp(consistency_hint(text))
        self_correction = _clamp(len(re.findall(r"\b(correct|clarify|rephrase|actually)\b", text, re.IGNORECASE)) / max(len(sentences), 1))
        transparency = _clamp((hedges + self_correction) / max(len(sentences), 1))
        confidence_score = _clamp(min(0.65, 0.3 + word_count / 1000))

        notes = (
            f"{notes_prefix} Detected a {'formal' if formality > 0.6 else 'mixed' if formality > 0.4 else 'casual'} tone, "
            f"{'higher' if reasoning_depth > 0.6 else 'moderate'} reasoning depth, and "
            f"{'expressive' if extraversion > 0.6 else 'measured'} delivery."
        )

        return StyleAnalysis(
            formality=formality,
            creativity=creativity,
            humor=humor,
            verbosity=verbosity,
            empathy=empathy,
            confidence=confidence,
            openness=openness,
            conscientiousness=conscientiousness,
            extraversion=extraversion,
            agreeableness=agreeableness,
            neuroticism=neuroticism,
            reasoning_depth=reasoning_depth,
            step_by_step=step_by_step,
            creativity_in_reasoning=creativity_in_reasoning,
            synthetics=synthetics,
            abstraction=abstraction,
            patterns=patterns,
            accuracy=accuracy,
            reliability=reliability,
            caution=caution,
            consistency=consistency,
            self_correction=self_correction,
            transparency=transparency,
            confidence_score=confidence_score,
            notes=notes,
        )


def consistency_hint(text: str) -> float:
    lower = text.lower()
    repeated_transitions = len(re.findall(r"\b(for example|for instance|however|therefore|because)\b", lower))
    repeated_phrases = len(re.findall(r"\b(again|consistently|always|usually)\b", lower))
    return _clamp(0.45 + repeated_transitions * 0.05 + repeated_phrases * 0.07)