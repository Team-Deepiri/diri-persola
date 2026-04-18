from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field
from datetime import datetime
from enum import Enum


class PresetName(str, Enum):
    DEFAULT = "default"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    TECHNICAL = "technical"
    EDUCATIONAL = "educational"


class CommunicationStyle(BaseModel):
    creativity: float = Field(default=0.5, ge=0.0, le=1.0)
    humor: float = Field(default=0.5, ge=0.0, le=1.0)
    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PersonalityTraits(BaseModel):
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)


class CognitiveStyle(BaseModel):
    reasoning_depth: float = Field(default=0.5, ge=0.0, le=1.0)
    step_by_step: float = Field(default=0.5, ge=0.0, le=1.0)
    creativity_in_reasoning: float = Field(default=0.5, ge=0.0, le=1.0)
    synthetics: float = Field(default=0.5, ge=0.0, le=1.0)
    abstraction: float = Field(default=0.5, ge=0.0, le=1.0)
    patterns: float = Field(default=0.5, ge=0.0, le=1.0)


class ReliabilityProfile(BaseModel):
    accuracy: float = Field(default=0.8, ge=0.0, le=1.0)
    reliability: float = Field(default=0.8, ge=0.0, le=1.0)
    caution: float = Field(default=0.5, ge=0.0, le=1.0)
    consistency: float = Field(default=0.8, ge=0.0, le=1.0)
    self_correction: float = Field(default=0.5, ge=0.0, le=1.0)
    transparency: float = Field(default=0.5, ge=0.0, le=1.0)


class ModelSettings(BaseModel):
    system_prompt: str = ""
    model: str = "llama3:8b"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1, le=32000)


class AgentTool(BaseModel):
    name: str
    enabled: bool = True
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)


class AgentMemoryPolicy(BaseModel):
    enabled: bool = True
    session_scope: str = "conversation"
    history_window: int = Field(default=50, ge=1, le=1000)


PERSONA_KNOB_GROUPS: Dict[str, tuple[str, ...]] = {
    "communication": ("creativity", "humor", "formality", "verbosity", "empathy", "confidence"),
    "personality": ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"),
    "cognitive": (
        "reasoning_depth",
        "step_by_step",
        "creativity_in_reasoning",
        "synthetics",
        "abstraction",
        "patterns",
    ),
    "reliability": ("accuracy", "reliability", "caution", "consistency", "self_correction", "transparency"),
}


class PersonaProfile(BaseModel):
    id: str = Field(default_factory=lambda: f"persona_{datetime.utcnow().timestamp()}")
    name: str = Field(default="Untitled Persona", max_length=200)
    description: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    creativity: float = Field(default=0.5, ge=0.0, le=1.0)
    humor: float = Field(default=0.5, ge=0.0, le=1.0)
    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)
    
    reasoning_depth: float = Field(default=0.5, ge=0.0, le=1.0)
    step_by_step: float = Field(default=0.5, ge=0.0, le=1.0)
    creativity_in_reasoning: float = Field(default=0.5, ge=0.0, le=1.0)
    synthetics: float = Field(default=0.5, ge=0.0, le=1.0)
    abstraction: float = Field(default=0.5, ge=0.0, le=1.0)
    patterns: float = Field(default=0.5, ge=0.0, le=1.0)
    
    accuracy: float = Field(default=0.8, ge=0.0, le=1.0)
    reliability: float = Field(default=0.8, ge=0.0, le=1.0)
    caution: float = Field(default=0.5, ge=0.0, le=1.0)
    consistency: float = Field(default=0.8, ge=0.0, le=1.0)
    self_correction: float = Field(default=0.5, ge=0.0, le=1.0)
    transparency: float = Field(default=0.5, ge=0.0, le=1.0)
    
    system_prompt: str = ""
    model: str = "llama3:8b"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1, le=32000)

    @computed_field(return_type=CommunicationStyle)
    def communication_style(self) -> CommunicationStyle:
        return CommunicationStyle(**{key: getattr(self, key) for key in PERSONA_KNOB_GROUPS["communication"]})

    @computed_field(return_type=PersonalityTraits)
    def personality_traits(self) -> PersonalityTraits:
        return PersonalityTraits(**{key: getattr(self, key) for key in PERSONA_KNOB_GROUPS["personality"]})

    @computed_field(return_type=CognitiveStyle)
    def cognitive_style(self) -> CognitiveStyle:
        return CognitiveStyle(**{key: getattr(self, key) for key in PERSONA_KNOB_GROUPS["cognitive"]})

    @computed_field(return_type=ReliabilityProfile)
    def reliability_profile(self) -> ReliabilityProfile:
        return ReliabilityProfile(**{key: getattr(self, key) for key in PERSONA_KNOB_GROUPS["reliability"]})

    @computed_field(return_type=ModelSettings)
    def model_settings(self) -> ModelSettings:
        return ModelSettings(
            system_prompt=self.system_prompt,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    @computed_field(return_type=Dict[str, float])
    def knobs(self) -> Dict[str, float]:
        return self.get_knobs()

    @classmethod
    def from_components(
        cls,
        *,
        name: str,
        description: str = "",
        communication: CommunicationStyle | None = None,
        personality: PersonalityTraits | None = None,
        cognitive: CognitiveStyle | None = None,
        reliability: ReliabilityProfile | None = None,
        settings: ModelSettings | None = None,
    ) -> "PersonaProfile":
        communication = communication or CommunicationStyle()
        personality = personality or PersonalityTraits()
        cognitive = cognitive or CognitiveStyle()
        reliability = reliability or ReliabilityProfile()
        settings = settings or ModelSettings()
        return cls(
            name=name,
            description=description,
            system_prompt=settings.system_prompt,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            **communication.model_dump(),
            **personality.model_dump(),
            **cognitive.model_dump(),
            **reliability.model_dump(),
        )

    def get_knobs(self) -> Dict[str, float]:
        return {
            "creativity": self.creativity,
            "humor": self.humor,
            "formality": self.formality,
            "verbosity": self.verbosity,
            "empathy": self.empathy,
            "confidence": self.confidence,
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
            "reasoning_depth": self.reasoning_depth,
            "step_by_step": self.step_by_step,
            "creativity_in_reasoning": self.creativity_in_reasoning,
            "synthetics": self.synthetics,
            "abstraction": self.abstraction,
            "patterns": self.patterns,
            "accuracy": self.accuracy,
            "reliability": self.reliability,
            "caution": self.caution,
            "consistency": self.consistency,
            "self_correction": self.self_correction,
            "transparency": self.transparency,
        }

    def set_knobs(self, knobs: Dict[str, float]) -> None:
        for key, value in knobs.items():
            if hasattr(self, key):
                setattr(self, key, value)


DEFAULT_PRESETS: Dict[PresetName, PersonaProfile] = {
    PresetName.DEFAULT: PersonaProfile(
        name="Default Assistant",
        description="Balanced and versatile",
        creativity=0.5, humor=0.5, formality=0.5, verbosity=0.5,
        empathy=0.5, confidence=0.5, openness=0.5, conscientiousness=0.5,
        extraversion=0.5, agreeableness=0.5, neuroticism=0.5,
        reasoning_depth=0.5, step_by_step=0.5, creativity_in_reasoning=0.5,
        synthetics=0.5, abstraction=0.5, patterns=0.5,
        accuracy=0.8, reliability=0.8, caution=0.5, consistency=0.8,
        self_correction=0.5, transparency=0.5,
    ),
    PresetName.CREATIVE: PersonaProfile(
        name="Creative Writer",
        description="Imaginative and expressive",
        creativity=0.9, humor=0.7, formality=0.3, verbosity=0.7,
        empathy=0.6, confidence=0.6, openness=0.9, conscientiousness=0.4,
        extraversion=0.6, agreeableness=0.6, neuroticism=0.4,
        reasoning_depth=0.4, step_by_step=0.3, creativity_in_reasoning=0.9,
        synthetics=0.7, abstraction=0.8, patterns=0.5,
        accuracy=0.6, reliability=0.6, caution=0.3, consistency=0.5,
        self_correction=0.4, transparency=0.4,
    ),
    PresetName.ANALYTICAL: PersonaProfile(
        name="Analytical Expert",
        description="Logical and thorough",
        creativity=0.3, humor=0.2, formality=0.8, verbosity=0.6,
        empathy=0.4, confidence=0.8, openness=0.6, conscientiousness=0.9,
        extraversion=0.3, agreeableness=0.5, neuroticism=0.3,
        reasoning_depth=0.9, step_by_step=0.9, creativity_in_reasoning=0.3,
        synthetics=0.8, abstraction=0.8, patterns=0.9,
        accuracy=0.95, reliability=0.9, caution=0.8, consistency=0.9,
        self_correction=0.8, transparency=0.8,
    ),
    PresetName.FRIENDLY: PersonaProfile(
        name="Friendly Companion",
        description="Warm and approachable",
        creativity=0.5, humor=0.7, formality=0.2, verbosity=0.6,
        empathy=0.9, confidence=0.5, openness=0.7, conscientiousness=0.5,
        extraversion=0.8, agreeableness=0.9, neuroticism=0.3,
        reasoning_depth=0.4, step_by_step=0.4, creativity_in_reasoning=0.5,
        synthetics=0.4, abstraction=0.4, patterns=0.5,
        accuracy=0.7, reliability=0.7, caution=0.4, consistency=0.7,
        self_correction=0.5, transparency=0.6,
    ),
    PresetName.PROFESSIONAL: PersonaProfile(
        name="Professional Advisor",
        description="Business-appropriate and reliable",
        creativity=0.3, humor=0.2, formality=0.9, verbosity=0.5,
        empathy=0.5, confidence=0.8, openness=0.4, conscientiousness=0.9,
        extraversion=0.4, agreeableness=0.6, neuroticism=0.2,
        reasoning_depth=0.8, step_by_step=0.8, creativity_in_reasoning=0.3,
        synthetics=0.7, abstraction=0.6, patterns=0.7,
        accuracy=0.9, reliability=0.95, caution=0.8, consistency=0.95,
        self_correction=0.7, transparency=0.8,
    ),
    PresetName.CASUAL: PersonaProfile(
        name="Casual Chat",
        description="Relaxed and informal",
        creativity=0.6, humor=0.8, formality=0.1, verbosity=0.7,
        empathy=0.7, confidence=0.5, openness=0.7, conscientiousness=0.3,
        extraversion=0.8, agreeableness=0.7, neuroticism=0.4,
        reasoning_depth=0.3, step_by_step=0.3, creativity_in_reasoning=0.6,
        synthetics=0.3, abstraction=0.3, patterns=0.4,
        accuracy=0.6, reliability=0.6, caution=0.2, consistency=0.5,
        self_correction=0.4, transparency=0.5,
    ),
    PresetName.TECHNICAL: PersonaProfile(
        name="Technical Expert",
        description="Precise and technical",
        creativity=0.4, humor=0.2, formality=0.8, verbosity=0.6,
        empathy=0.3, confidence=0.9, openness=0.7, conscientiousness=0.9,
        extraversion=0.3, agreeableness=0.4, neuroticism=0.2,
        reasoning_depth=0.95, step_by_step=0.95, creativity_in_reasoning=0.4,
        synthetics=0.9, abstraction=0.9, patterns=0.9,
        accuracy=0.95, reliability=0.95, caution=0.9, consistency=0.95,
        self_correction=0.9, transparency=0.9,
    ),
    PresetName.EDUCATIONAL: PersonaProfile(
        name="Tutor",
        description="Patient and instructional",
        creativity=0.5, humor=0.4, formality=0.5, verbosity=0.7,
        empathy=0.9, confidence=0.6, openness=0.7, conscientiousness=0.8,
        extraversion=0.6, agreeableness=0.9, neuroticism=0.2,
        reasoning_depth=0.7, step_by_step=0.9, creativity_in_reasoning=0.5,
        synthetics=0.6, abstraction=0.6, patterns=0.7,
        accuracy=0.9, reliability=0.9, caution=0.6, consistency=0.9,
        self_correction=0.8, transparency=0.9,
    ),
}


class AgentConfig(BaseModel):
    agent_id: str = Field(default_factory=lambda: f"agent_{datetime.utcnow().timestamp()}")
    name: str = Field(default="Persola Agent", max_length=200)
    role: str = "assistant"
    model: str = "llama3:8b"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = ""
    persona_id: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    memory_enabled: bool = True
    session_id: Optional[str] = None

    @computed_field(return_type=List[AgentTool])
    def tool_configs(self) -> List[AgentTool]:
        return [AgentTool(name=tool_name) for tool_name in self.tools]

    @computed_field(return_type=AgentMemoryPolicy)
    def memory_policy(self) -> AgentMemoryPolicy:
        return AgentMemoryPolicy(enabled=self.memory_enabled)


class KnobDefinition(BaseModel):
    key: str
    name: str
    description: str
    min_value: float = 0.0
    max_value: float = 1.0
    default: float = 0.5
    panel: str
    step: float = 0.05


KNOB_DEFINITIONS: List[KnobDefinition] = [
    KnobDefinition(key="creativity", name="Creativity", description="How creative and imaginative the responses are", panel="Creativity"),
    KnobDefinition(key="humor", name="Humor", description="Use of humor in responses", panel="Creativity"),
    KnobDefinition(key="formality", name="Formality", description="Formality level of communication", panel="Creativity"),
    KnobDefinition(key="verbosity", name="Verbosity", description="Length and detail of responses", panel="Creativity"),
    KnobDefinition(key="empathy", name="Empathy", description="Emotional understanding and acknowledgment", panel="Creativity"),
    KnobDefinition(key="confidence", name="Confidence", description="Certainty and assertiveness in responses", panel="Creativity"),
    
    KnobDefinition(key="openness", name="Openness", description="Receptivity to new ideas and experiences", panel="Personality"),
    KnobDefinition(key="conscientiousness", name="Conscientiousness", description="Organization and dependability", panel="Personality"),
    KnobDefinition(key="extraversion", name="Extraversion", description="Sociability and energy in interactions", panel="Personality"),
    KnobDefinition(key="agreeableness", name="Agreeableness", description="Cooperation and trustworthiness", panel="Personality"),
    KnobDefinition(key="neuroticism", name="Neuroticism", description="Emotional stability vs reactivity", panel="Personality"),
    
    KnobDefinition(key="reasoning_depth", name="Reasoning Depth", description="Depth of analytical thinking", panel="Thinking"),
    KnobDefinition(key="step_by_step", name="Step-by-Step", description="Structured logical approach", panel="Thinking"),
    KnobDefinition(key="creativity_in_reasoning", name="Creative Reasoning", description="Novel approaches to problem solving", panel="Thinking"),
    KnobDefinition(key="synthetics", name="Synthesis", description="Combining ideas from multiple sources", panel="Thinking"),
    KnobDefinition(key="abstraction", name="Abstraction", description="Working with abstract concepts", panel="Thinking"),
    KnobDefinition(key="patterns", name="Pattern Recognition", description="Identifying patterns in information", panel="Thinking"),
    
    KnobDefinition(key="accuracy", name="Accuracy", description="Factual correctness of responses", panel="Reliability", default=0.8),
    KnobDefinition(key="reliability", name="Reliability", description="Consistency of response quality", panel="Reliability", default=0.8),
    KnobDefinition(key="caution", name="Caution", description="Carefulness in uncertain situations", panel="Reliability"),
    KnobDefinition(key="consistency", name="Consistency", description="Uniformity in behavior and responses", panel="Reliability", default=0.8),
    KnobDefinition(key="self_correction", name="Self-Correction", description="Ability to identify and fix errors", panel="Reliability"),
    KnobDefinition(key="transparency", name="Transparency", description="Openness about limitations and uncertainty", panel="Reliability"),
]
