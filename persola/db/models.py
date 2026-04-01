from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
	versions: Mapped[list["PersonaVersionModel"]] = relationship(back_populates="persona", cascade="all, delete-orphan")
	analysis_runs: Mapped[list["AnalysisRunModel"]] = relationship(back_populates="persona")


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
	tool_configs: Mapped[list["AgentToolModel"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
	runs: Mapped[list["AgentRunModel"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


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
	runs: Mapped[list["AgentRunModel"]] = relationship(back_populates="session")


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


class PersonaVersionModel(Base):
	__tablename__ = "persona_versions"
	__table_args__ = (
		Index("idx_persona_versions_persona_id", "persona_id"),
		UniqueConstraint("persona_id", "version_number", name="uq_persona_version_number"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	persona_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("personas.id", ondelete="CASCADE"),
		nullable=False,
	)
	version_number: Mapped[int] = mapped_column(Integer, nullable=False)
	source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	knob_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

	persona: Mapped["PersonaModel"] = relationship(back_populates="versions")


class AgentToolModel(Base):
	__tablename__ = "agent_tools"
	__table_args__ = (
		Index("idx_agent_tools_agent_id", "agent_id"),
		UniqueConstraint("agent_id", "name", name="uq_agent_tool_name"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	tool_config: Mapped[dict[str, Any]] = mapped_column("config", JSONB, nullable=False, default=dict)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime,
		nullable=False,
		default=datetime.utcnow,
		onupdate=datetime.utcnow,
	)

	agent: Mapped["AgentModel"] = relationship(back_populates="tool_configs")


class AnalysisRunModel(Base):
	__tablename__ = "analysis_runs"
	__table_args__ = (
		Index("idx_analysis_runs_persona_id", "persona_id"),
		Index("idx_analysis_runs_created_at", "created_at"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	persona_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("personas.id", ondelete="SET NULL"),
		nullable=True,
	)
	source_text: Mapped[str] = mapped_column(Text, nullable=False)
	knobs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
	notes: Mapped[str | None] = mapped_column(Text, nullable=True)
	provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
	model: Mapped[str | None] = mapped_column(String(100), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

	persona: Mapped["PersonaModel | None"] = relationship(back_populates="analysis_runs")


class AgentRunModel(Base):
	__tablename__ = "agent_runs"
	__table_args__ = (
		Index("idx_agent_runs_agent_id", "agent_id"),
		Index("idx_agent_runs_session_id", "session_id"),
		Index("idx_agent_runs_created_at", "created_at"),
	)

	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	session_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("sessions.id", ondelete="SET NULL"),
		nullable=True,
	)
	status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
	provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
	model: Mapped[str | None] = mapped_column(String(100), nullable=True)
	request_message: Mapped[str] = mapped_column(Text, nullable=False)
	response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
	tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
	run_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
	completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	agent: Mapped["AgentModel"] = relationship(back_populates="runs")
	session: Mapped["SessionModel | None"] = relationship(back_populates="runs")
