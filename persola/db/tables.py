"""
SQLAlchemy ORM tables for Deepiri Persola.

PersonaRow mirrors the existing PersonaProfile Pydantic model field-for-field
so conversion is straightforward.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PersonaRow(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Persona")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ── 23 Tunable Knobs (individual columns — matches PersonaProfile) ───
    # Creativity & Communication
    creativity: Mapped[float] = mapped_column(Float, default=0.5)
    humor: Mapped[float] = mapped_column(Float, default=0.5)
    formality: Mapped[float] = mapped_column(Float, default=0.5)
    verbosity: Mapped[float] = mapped_column(Float, default=0.5)
    empathy: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    # Personality (Big Five)
    openness: Mapped[float] = mapped_column(Float, default=0.5)
    conscientiousness: Mapped[float] = mapped_column(Float, default=0.5)
    extraversion: Mapped[float] = mapped_column(Float, default=0.5)
    agreeableness: Mapped[float] = mapped_column(Float, default=0.5)
    neuroticism: Mapped[float] = mapped_column(Float, default=0.5)

    # Thinking Style
    reasoning_depth: Mapped[float] = mapped_column(Float, default=0.5)
    step_by_step: Mapped[float] = mapped_column(Float, default=0.5)
    creativity_in_reasoning: Mapped[float] = mapped_column(Float, default=0.5)
    synthetics: Mapped[float] = mapped_column(Float, default=0.5)
    abstraction: Mapped[float] = mapped_column(Float, default=0.5)
    patterns: Mapped[float] = mapped_column(Float, default=0.5)

    # Reliability & Accuracy
    accuracy: Mapped[float] = mapped_column(Float, default=0.8)
    reliability: Mapped[float] = mapped_column(Float, default=0.8)
    caution: Mapped[float] = mapped_column(Float, default=0.5)
    consistency: Mapped[float] = mapped_column(Float, default=0.8)
    self_correction: Mapped[float] = mapped_column(Float, default=0.5)
    transparency: Mapped[float] = mapped_column(Float, default=0.5)

    # ── LLM Config ───────────────────────────────────────────────────────
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(128), default="llama3:8b")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2000)

    # ── Metadata ─────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    # ── Relationships ────────────────────────────────────────────────────
    writing_samples: Mapped[list["WritingSampleRow"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<PersonaRow {self.name!r} id={self.id}>"


class WritingSampleRow(Base):
    """Uploaded writing samples for style analysis (T2.2, T2.3, T2.4)."""
    __tablename__ = "writing_samples"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"ws_{uuid.uuid4().hex[:8]}")
    persona_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    persona: Mapped["PersonaRow"] = relationship(back_populates="writing_samples")


class AgentRow(Base):
    """Agent configuration persisted to Postgres."""
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Persola Agent")
    role: Mapped[str] = mapped_column(String(100), nullable=False, default="assistant")
    model: Mapped[str] = mapped_column(String(128), default="llama3:8b")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2000)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    persona_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tools: Mapped[list | None] = mapped_column(JSONB, default=list)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    persona: Mapped["PersonaRow"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<AgentRow {self.name!r} id={self.agent_id}>"