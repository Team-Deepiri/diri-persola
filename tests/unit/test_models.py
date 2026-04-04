"""Unit tests for Pydantic model validation and computed fields."""

import pytest
from pydantic import ValidationError

from persola.models import (
    AgentConfig,
    AgentMemoryPolicy,
    CommunicationStyle,
    PersonaProfile,
    PresetName,
)


# ---------------------------------------------------------------------------
# PersonaProfile – knob field constraints
# ---------------------------------------------------------------------------

class TestPersonaProfileKnobs:
    def test_default_knobs_in_range(self):
        p = PersonaProfile(name="P")
        for key, val in p.get_knobs().items():
            assert 0.0 <= val <= 1.0, f"Default knob '{key}' = {val} out of range"

    def test_knob_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            PersonaProfile(name="P", creativity=-0.01)

    def test_knob_above_one_rejected(self):
        with pytest.raises(ValidationError):
            PersonaProfile(name="P", humor=1.01)

    def test_boundary_value_zero_accepted(self):
        p = PersonaProfile(name="P", creativity=0.0)
        assert p.creativity == 0.0

    def test_boundary_value_one_accepted(self):
        p = PersonaProfile(name="P", humor=1.0)
        assert p.humor == 1.0

    def test_get_knobs_returns_all_23_keys(self):
        assert len(PersonaProfile(name="P").get_knobs()) == 23


# ---------------------------------------------------------------------------
# PersonaProfile – text field constraints
# ---------------------------------------------------------------------------

class TestPersonaProfileTextFields:
    def test_name_max_200_rejected(self):
        with pytest.raises(ValidationError):
            PersonaProfile(name="x" * 201)

    def test_name_at_200_accepted(self):
        p = PersonaProfile(name="x" * 200)
        assert len(p.name) == 200

    def test_description_max_2000_rejected(self):
        with pytest.raises(ValidationError):
            PersonaProfile(name="P", description="x" * 2001)

    def test_description_at_2000_accepted(self):
        p = PersonaProfile(name="P", description="x" * 2000)
        assert len(p.description) == 2000


# ---------------------------------------------------------------------------
# PersonaProfile – computed fields
# ---------------------------------------------------------------------------

class TestPersonaProfileComputedFields:
    def test_communication_style_reflects_knobs(self):
        p = PersonaProfile(name="P", creativity=0.9, humor=0.1)
        assert abs(p.communication_style.creativity - 0.9) < 0.001
        assert abs(p.communication_style.humor - 0.1) < 0.001

    def test_knobs_property_matches_get_knobs(self):
        p = PersonaProfile(name="P", creativity=0.75)
        assert p.knobs["creativity"] == p.get_knobs()["creativity"]

    def test_model_settings_reflects_fields(self):
        p = PersonaProfile(name="P", temperature=1.2, max_tokens=512)
        assert abs(p.model_settings.temperature - 1.2) < 0.001
        assert p.model_settings.max_tokens == 512


# ---------------------------------------------------------------------------
# PersonaProfile – set_knobs
# ---------------------------------------------------------------------------

class TestPersonaProfileSetKnobs:
    def test_set_knobs_updates_fields(self):
        p = PersonaProfile(name="P")
        p.set_knobs({"creativity": 0.9, "humor": 0.1})
        assert abs(p.creativity - 0.9) < 0.001
        assert abs(p.humor - 0.1) < 0.001

    def test_set_knobs_does_not_affect_other_fields(self):
        p = PersonaProfile(name="P", formality=0.3)
        p.set_knobs({"creativity": 0.8})
        assert abs(p.formality - 0.3) < 0.001


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------

class TestAgentConfig:
    def test_defaults(self):
        a = AgentConfig(name="Agent")
        assert a.role == "assistant"
        assert a.model == "llama3:8b"
        assert a.memory_enabled is True

    def test_name_max_200_rejected(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="x" * 201)

    def test_tool_configs_computed_field(self):
        a = AgentConfig(name="A", tools=["search", "code"])
        assert len(a.tool_configs) == 2
        assert a.tool_configs[0].name == "search"

    def test_memory_policy_computed_field_disabled(self):
        a = AgentConfig(name="A", memory_enabled=False)
        assert a.memory_policy.enabled is False


# ---------------------------------------------------------------------------
# AgentMemoryPolicy
# ---------------------------------------------------------------------------

class TestAgentMemoryPolicy:
    def test_history_window_zero_rejected(self):
        with pytest.raises(ValidationError):
            AgentMemoryPolicy(history_window=0)

    def test_history_window_over_1000_rejected(self):
        with pytest.raises(ValidationError):
            AgentMemoryPolicy(history_window=1001)

    def test_history_window_at_boundaries_accepted(self):
        assert AgentMemoryPolicy(history_window=1).history_window == 1
        assert AgentMemoryPolicy(history_window=1000).history_window == 1000
