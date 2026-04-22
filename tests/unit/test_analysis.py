"""Unit tests for writing style extraction and prompt building."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from persola.analysis.extractor import StyleAnalysis, WritingStyleExtractor
from persola.analysis.mapper import StyleToKnobMapper
from persola.analysis.prompts import build_analysis_prompt, build_analysis_retry_prompt


SAMPLE_TEXT = (
    "The experiment demonstrated a statistically significant correlation between "
    "neural activity patterns and behavioural outcomes. Further analysis is required "
    "to establish causality. We recommend a controlled longitudinal study with "
    "adequate sample size and pre-registered hypotheses."
)

_ALL_KNOB_KEYS = (
    "creativity", "humor", "formality", "verbosity", "empathy", "confidence",
    "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism",
    "reasoning_depth", "step_by_step", "creativity_in_reasoning", "synthetics",
    "abstraction", "patterns", "accuracy", "reliability", "caution",
    "consistency", "self_correction", "transparency",
)

_MOCK_LLM_PAYLOAD = {k: 0.5 for k in _ALL_KNOB_KEYS}
_MOCK_LLM_PAYLOAD.update(
    {"formality": 0.9, "creativity": 0.3, "confidence_score": 0.92, "notes": "Formal analytical"}
)


# ---------------------------------------------------------------------------
# StyleAnalysis dataclass
# ---------------------------------------------------------------------------

class TestStyleAnalysis:
    def test_to_knob_dict_returns_23_keys(self):
        knobs = StyleAnalysis().to_knob_dict()
        assert len(knobs) == 23

    def test_all_default_values_in_range(self):
        for key, val in StyleAnalysis().to_knob_dict().items():
            assert 0.0 <= val <= 1.0, f"'{key}' = {val} out of [0, 1]"

    def test_from_payload_parses_known_field(self):
        analysis = StyleAnalysis.from_payload({"creativity": 0.9})
        assert abs(analysis.creativity - 0.9) < 0.001

    def test_from_payload_clamps_over_range(self):
        analysis = StyleAnalysis.from_payload({"creativity": 1.8})
        assert analysis.creativity <= 1.0

    def test_from_payload_clamps_under_range(self):
        analysis = StyleAnalysis.from_payload({"humor": -0.5})
        assert analysis.humor >= 0.0

    def test_knob_keys_returns_23_items(self):
        assert len(StyleAnalysis.knob_keys()) == 23


# ---------------------------------------------------------------------------
# WritingStyleExtractor – heuristic path (LLM unavailable)
# ---------------------------------------------------------------------------

class TestWritingStyleExtractorHeuristic:
    @pytest.fixture()
    def extractor(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = False
        return WritingStyleExtractor(llm=mock_llm)

    async def test_extract_returns_style_analysis(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        assert isinstance(result, StyleAnalysis)

    async def test_extract_all_knobs_in_range(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        for key, val in result.to_knob_dict().items():
            assert 0.0 <= val <= 1.0, f"Heuristic knob '{key}' = {val} out of range"

    async def test_extract_has_confidence_score(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        assert 0.0 <= result.confidence_score <= 1.0

    async def test_extract_empty_text_raises(self, extractor):
        with pytest.raises((ValueError, Exception)):
            await extractor.extract("   ")

    async def test_extract_uses_heuristic_notes(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        assert isinstance(result.notes, str)


# ---------------------------------------------------------------------------
# WritingStyleExtractor – LLM path (mock LLM)
# ---------------------------------------------------------------------------

class TestWritingStyleExtractorWithMockLLM:
    @pytest.fixture()
    def extractor(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate = AsyncMock(return_value=json.dumps(_MOCK_LLM_PAYLOAD))
        return WritingStyleExtractor(llm=mock_llm)

    async def test_extract_parses_llm_response(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        assert isinstance(result, StyleAnalysis)
        assert abs(result.formality - 0.9) < 0.001
        assert abs(result.creativity - 0.3) < 0.001

    async def test_extract_confidence_from_llm(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        assert abs(result.confidence_score - 0.92) < 0.001

    async def test_llm_generate_called_once(self, extractor):
        await extractor.extract(SAMPLE_TEXT)
        extractor.llm.generate.assert_called_once()

    async def test_extract_all_knobs_in_range_with_llm(self, extractor):
        result = await extractor.extract(SAMPLE_TEXT)
        for key, val in result.to_knob_dict().items():
            assert 0.0 <= val <= 1.0, f"LLM knob '{key}' = {val} out of range"


# ---------------------------------------------------------------------------
# StyleToKnobMapper
# ---------------------------------------------------------------------------

class TestStyleToKnobMapper:
    @pytest.fixture()
    def mapper(self):
        return StyleToKnobMapper()

    def test_map_returns_23_keys(self, mapper):
        assert len(mapper.map(StyleAnalysis())) == 23

    def test_map_preserves_field_values(self, mapper):
        analysis = StyleAnalysis(creativity=0.77, formality=0.23)
        result = mapper.map(analysis)
        assert abs(result["creativity"] - 0.77) < 0.001
        assert abs(result["formality"] - 0.23) < 0.001

    def test_all_mapped_values_in_range(self, mapper):
        for val in mapper.map(StyleAnalysis()).values():
            assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

class TestPromptBuilders:
    def test_analysis_prompt_contains_sample_text(self):
        prompt = build_analysis_prompt(SAMPLE_TEXT)
        assert SAMPLE_TEXT in prompt

    def test_analysis_prompt_is_non_empty(self):
        assert len(build_analysis_prompt(SAMPLE_TEXT).strip()) > 100

    def test_retry_prompt_contains_original_text(self):
        invalid = '{"creativity": "bad"}'
        assert SAMPLE_TEXT in build_analysis_retry_prompt(SAMPLE_TEXT, invalid)

    def test_retry_prompt_contains_invalid_response(self):
        invalid = '{"creativity": "bad"}'
        assert invalid in build_analysis_retry_prompt(SAMPLE_TEXT, invalid)
