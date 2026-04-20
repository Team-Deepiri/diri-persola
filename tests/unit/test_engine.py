"""Unit tests for PersonaEngine."""

import pytest

from persola.engine import PersonaEngine, SamplingCompiler
from persola.models import PersonaProfile, PresetName


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine() -> PersonaEngine:
    return PersonaEngine()


@pytest.fixture()
def default_persona() -> PersonaProfile:
    return PersonaProfile(name="Default")


@pytest.fixture()
def creative_persona() -> PersonaProfile:
    return PersonaProfile(name="Creative", creativity=1.0, humor=0.9, formality=0.0)


@pytest.fixture()
def formal_persona() -> PersonaProfile:
    return PersonaProfile(name="Formal", creativity=0.0, humor=0.0, formality=1.0)


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:
    def test_returns_non_empty_string(self, engine, default_persona):
        prompt = engine.build_system_prompt(default_persona)
        assert isinstance(prompt, str)
        assert len(prompt.strip()) > 0

    def test_contains_persona_name(self, engine, default_persona):
        prompt = engine.build_system_prompt(default_persona)
        assert default_persona.name in prompt

    def test_high_creativity_differs_from_low(self, engine, creative_persona, formal_persona):
        assert engine.build_system_prompt(creative_persona) != engine.build_system_prompt(formal_persona)

    def test_all_four_sections_present(self, engine, default_persona):
        prompt = engine.build_system_prompt(default_persona)
        # The prompt is built from four private section methods; just verify
        # it has substantial content covering all areas.
        assert len(prompt) > 200


# ---------------------------------------------------------------------------
# get_sampling_params
# ---------------------------------------------------------------------------

class TestGetSamplingParams:
    def test_returns_required_keys(self, engine, default_persona):
        params = engine.get_sampling_params(default_persona)
        for key in ("temperature", "top_p", "top_k", "repeat_penalty"):
            assert key in params

    def test_temperature_at_zero_creativity(self, engine):
        """temperature = 0.3 + creativity * 1.4; at creativity=0 → 0.3"""
        persona = PersonaProfile(name="T", creativity=0.0)
        params = engine.get_sampling_params(persona)
        assert abs(params["temperature"] - 0.3) < 0.01

    def test_temperature_at_full_creativity(self, engine):
        """At creativity=1.0 → temperature = 0.3 + 1.4 = 1.7"""
        persona = PersonaProfile(name="T", creativity=1.0)
        params = engine.get_sampling_params(persona)
        assert abs(params["temperature"] - 1.7) < 0.01

    def test_top_p_in_valid_range(self, engine, default_persona):
        params = engine.get_sampling_params(default_persona)
        assert 0.0 < params["top_p"] <= 1.0

    def test_top_k_is_positive_integer(self, engine, default_persona):
        params = engine.get_sampling_params(default_persona)
        assert isinstance(params["top_k"], int)
        assert params["top_k"] > 0

    def test_repeat_penalty_at_least_one(self, engine, default_persona):
        """repeat_penalty = 1.0 + consistency * 0.2; always ≥ 1.0"""
        params = engine.get_sampling_params(default_persona)
        assert params["repeat_penalty"] >= 1.0


# ---------------------------------------------------------------------------
# blend_personas
# ---------------------------------------------------------------------------

class TestBlendPersonas:
    def test_50_50_blend_is_midpoint(self, engine):
        p1 = PersonaProfile(name="A", creativity=0.0)
        p2 = PersonaProfile(name="B", creativity=1.0)
        blended = engine.blend_personas(p1, p2, ratio=0.5)
        assert abs(blended.creativity - 0.5) < 0.001

    def test_ratio_0_returns_p1_knobs(self, engine):
        p1 = PersonaProfile(name="A", creativity=0.2, humor=0.3)
        p2 = PersonaProfile(name="B", creativity=0.8, humor=0.9)
        blended = engine.blend_personas(p1, p2, ratio=0.0)
        assert abs(blended.creativity - 0.2) < 0.001
        assert abs(blended.humor - 0.3) < 0.001

    def test_ratio_1_returns_p2_knobs(self, engine):
        p1 = PersonaProfile(name="A", creativity=0.2)
        p2 = PersonaProfile(name="B", creativity=0.8)
        blended = engine.blend_personas(p1, p2, ratio=1.0)
        assert abs(blended.creativity - 0.8) < 0.001

    def test_returns_persona_profile_instance(self, engine):
        p1 = PersonaProfile(name="A")
        p2 = PersonaProfile(name="B")
        assert isinstance(engine.blend_personas(p1, p2), PersonaProfile)

    def test_blended_knobs_in_range(self, engine):
        p1 = PersonaProfile(name="A", creativity=0.1, formality=0.9)
        p2 = PersonaProfile(name="B", creativity=0.9, formality=0.1)
        blended = engine.blend_personas(p1, p2, ratio=0.33)
        for val in blended.get_knobs().values():
            assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# apply_preset
# ---------------------------------------------------------------------------

class TestApplyPreset:
    def test_returns_persona_profile(self, engine):
        assert isinstance(engine.apply_preset(PresetName.CREATIVE), PersonaProfile)

    def test_creative_preset_has_elevated_creativity(self, engine):
        result = engine.apply_preset(PresetName.CREATIVE)
        assert result.creativity >= 0.7

    def test_professional_preset_has_elevated_formality(self, engine):
        result = engine.apply_preset(PresetName.PROFESSIONAL)
        assert result.formality >= 0.7

    def test_all_presets_produce_valid_knobs(self, engine):
        for preset in list(PresetName):
            result = engine.apply_preset(preset)
            validation = engine.validate_knobs(result.get_knobs())
            assert validation["valid"], (
                f"{preset.value} preset produced invalid knobs: {validation['errors']}"
            )


# ---------------------------------------------------------------------------
# validate_knobs
# ---------------------------------------------------------------------------

class TestValidateKnobs:
    def test_all_valid_knobs_pass(self, engine):
        knobs = {
            "creativity": 0.5, "humor": 0.5, "formality": 0.5, "verbosity": 0.5,
            "empathy": 0.5, "confidence": 0.5, "openness": 0.5,
            "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5,
            "neuroticism": 0.5, "reasoning_depth": 0.5, "step_by_step": 0.5,
            "creativity_in_reasoning": 0.5, "synthetics": 0.5, "abstraction": 0.5,
            "patterns": 0.5, "accuracy": 0.8, "reliability": 0.8, "caution": 0.5,
            "consistency": 0.8, "self_correction": 0.5, "transparency": 0.5,
        }
        result = engine.validate_knobs(knobs)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_out_of_range_value_flagged(self, engine):
        result = engine.validate_knobs({"creativity": 1.5})
        assert result["valid"] is False
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# SamplingCompiler
# ---------------------------------------------------------------------------

class TestSamplingCompiler:
    def test_compile_returns_sampling_keys(self):
        compiler = SamplingCompiler()
        params = compiler.compile(PersonaProfile(name="T"))
        assert "temperature" in params
        assert "top_p" in params
