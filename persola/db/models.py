from sqlalchemy import Column, String, Text, DateTime, Float, Integer, ForeignKey, Index, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class PersonaModel(Base):
    """SQLAlchemy model for persona profiles."""
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Tuning parameters
    creativity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    humor: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    formality: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    verbosity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    empathy: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    openness: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    conscientiousness: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    extraversion: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    agreeableness: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    neuroticism: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    reasoning_depth: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    step_by_step: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    creativity_in_reasoning: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    synthetics: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    abstraction: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    patterns: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    reliability: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    caution: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    consistency: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    self_correction: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    transparency: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    system_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False, default="llama3:8b")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)

    # Relationships
    agents: Mapped[list["AgentModel"]] = relationship("AgentModel", back_populates="persona", cascade="all, delete-orphan")
    sessions: Mapped[list["SessionModel"]] = relationship("SessionModel", back_populates="persona", cascade="all, delete-orphan")

    def get_knobs(self) -> Dict[str, float]:
        """Get all tuning parameters as a dictionary."""
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


    # Relationships
    agents: Mapped[list["AgentModel"]] = relationship("AgentModel", back_populates="persona", cascade="all, delete-orphan")
    sessions: Mapped[list["SessionModel"]] = relationship("SessionModel", back_populates="persona", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_personas_created_at', 'created_at'),
        Index('ix_personas_updated_at', 'updated_at'),
        Index('ix_personas_name', 'name'),
        # Check constraints for knob ranges
        CheckConstraint('creativity >= 0.0 AND creativity <= 1.0', name='ck_personas_creativity_range'),
        CheckConstraint('humor >= 0.0 AND humor <= 1.0', name='ck_personas_humor_range'),
        CheckConstraint('formality >= 0.0 AND formality <= 1.0', name='ck_personas_formality_range'),
        CheckConstraint('verbosity >= 0.0 AND verbosity <= 1.0', name='ck_personas_verbosity_range'),
        CheckConstraint('empathy >= 0.0 AND empathy <= 1.0', name='ck_personas_empathy_range'),
        CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='ck_personas_confidence_range'),
        CheckConstraint('openness >= 0.0 AND openness <= 1.0', name='ck_personas_openness_range'),
        CheckConstraint('conscientiousness >= 0.0 AND conscientiousness <= 1.0', name='ck_personas_conscientiousness_range'),
        CheckConstraint('extraversion >= 0.0 AND extraversion <= 1.0', name='ck_personas_extraversion_range'),
        CheckConstraint('agreeableness >= 0.0 AND agreeableness <= 1.0', name='ck_personas_agreeableness_range'),
        CheckConstraint('neuroticism >= 0.0 AND neuroticism <= 1.0', name='ck_personas_neuroticism_range'),
        CheckConstraint('reasoning_depth >= 0.0 AND reasoning_depth <= 1.0', name='ck_personas_reasoning_depth_range'),
        CheckConstraint('step_by_step >= 0.0 AND step_by_step <= 1.0', name='ck_personas_step_by_step_range'),
        CheckConstraint('creativity_in_reasoning >= 0.0 AND creativity_in_reasoning <= 1.0', name='ck_personas_creativity_in_reasoning_range'),
        CheckConstraint('synthetics >= 0.0 AND synthetics <= 1.0', name='ck_personas_synthetics_range'),
        CheckConstraint('abstraction >= 0.0 AND abstraction <= 1.0', name='ck_personas_abstraction_range'),
        CheckConstraint('patterns >= 0.0 AND patterns <= 1.0', name='ck_personas_patterns_range'),
        CheckConstraint('accuracy >= 0.0 AND accuracy <= 1.0', name='ck_personas_accuracy_range'),
        CheckConstraint('reliability >= 0.0 AND reliability <= 1.0', name='ck_personas_reliability_range'),
        CheckConstraint('caution >= 0.0 AND caution <= 1.0', name='ck_personas_caution_range'),
        CheckConstraint('consistency >= 0.0 AND consistency <= 1.0', name='ck_personas_consistency_range'),
        CheckConstraint('self_correction >= 0.0 AND self_correction <= 1.0', name='ck_personas_self_correction_range'),
        CheckConstraint('transparency >= 0.0 AND transparency <= 1.0', name='ck_personas_transparency_range'),
        CheckConstraint('temperature >= 0.0 AND temperature <= 2.0', name='ck_personas_temperature_range'),
        CheckConstraint('max_tokens >= 1 AND max_tokens <= 32000', name='ck_personas_max_tokens_range'),
    )


class AgentModel(Base):
    """SQLAlchemy model for agent configurations."""
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Relationships
    persona: Mapped["PersonaModel"] = relationship("PersonaModel", back_populates="agents")
    sessions: Mapped[list["SessionModel"]] = relationship("SessionModel", back_populates="agent", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_agents_persona_id', 'persona_id'),
        Index('ix_agents_created_at', 'created_at'),
        Index('ix_agents_name', 'name'),
        Index('ix_agents_is_active', 'is_active'),
    )


class SessionModel(Base):
    """SQLAlchemy model for conversation sessions."""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), nullable=True)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=True, default=dict)

    # Relationships
    persona: Mapped["PersonaModel"] = relationship("PersonaModel", back_populates="sessions")
    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="sessions")
    messages: Mapped[list["MessageModel"]] = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan", order_by="MessageModel.timestamp")

    # Indexes
    __table_args__ = (
        Index('ix_sessions_persona_id', 'persona_id'),
        Index('ix_sessions_agent_id', 'agent_id'),
        Index('ix_sessions_started_at', 'started_at'),
        Index('ix_sessions_user_id', 'user_id'),
    )


class MessageModel(Base):
    """SQLAlchemy model for individual messages."""
    __tablename__ = "conversation_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=True, default=dict)

    # Relationships
    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index('ix_conversation_history_session_id', 'session_id'),
        Index('ix_conversation_history_timestamp', 'timestamp'),
        Index('ix_conversation_history_role', 'role'),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name='ck_conversation_history_role'),
    )


class PersonaPresetModel(Base):
    """SQLAlchemy model for persona preset templates."""
    __tablename__ = "persona_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    preset_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Indexes
    __table_args__ = (
        Index('ix_persona_presets_name', 'name'),
        Index('ix_persona_presets_is_default', 'is_default'),
    )