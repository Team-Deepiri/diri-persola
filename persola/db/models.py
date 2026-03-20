from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
	pass


class PersonaModel(Base):
	__tablename__ = "personas"
	__table_args__ = (
		Index("idx_personas_name", "name"),
		Index("idx_personas_is_preset", "is_preset"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)

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

	model: Mapped[str] = mapped_column(String(100), nullable=False, default="llama3:8b")
	temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
	max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
	is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime,
		nullable=False,
		default=datetime.utcnow,
		onupdate=datetime.utcnow,
	)

	agents: Mapped[list["AgentModel"]] = relationship(back_populates="persona")


class AgentModel(Base):
	__tablename__ = "agents"
	__table_args__ = (Index("idx_agents_persona_id", "persona_id"),)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	role: Mapped[str] = mapped_column(String(100), nullable=False, default="assistant")
	model: Mapped[str | None] = mapped_column(String(100), nullable=True)
	temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
	max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
	system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
	persona_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("personas.id", ondelete="SET NULL"),
		nullable=True,
	)
	tools: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
	memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime,
		nullable=False,
		default=datetime.utcnow,
		onupdate=datetime.utcnow,
	)

	persona: Mapped["PersonaModel | None"] = relationship(back_populates="agents")
	sessions: Mapped[list["SessionModel"]] = relationship(back_populates="agent")


class SessionModel(Base):
	__tablename__ = "sessions"
	__table_args__ = (
		Index("idx_sessions_agent_id", "agent_id"),
		Index("idx_sessions_session_id", "session_id"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	session_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
	session_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
	message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

	agent: Mapped["AgentModel"] = relationship(back_populates="sessions")
	messages: Mapped[list["MessageModel"]] = relationship(back_populates="session")


class MessageModel(Base):
	__tablename__ = "messages"
	__table_args__ = (
		Index("idx_messages_session_id", "session_id"),
		Index("idx_messages_created_at", "created_at"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	session_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("sessions.id", ondelete="CASCADE"),
		nullable=False,
	)
	role: Mapped[str] = mapped_column(String(20), nullable=False)
	content: Mapped[str] = mapped_column(Text, nullable=False)
	message_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
	tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
	model: Mapped[str | None] = mapped_column(String(100), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

	session: Mapped["SessionModel"] = relationship(back_populates="messages")
