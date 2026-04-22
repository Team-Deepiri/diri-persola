from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
	pass


PERSONA_KNOB_FIELDS: tuple[str, ...] = (
	"creativity",
	"humor",
	"formality",
	"verbosity",
	"empathy",
	"confidence",
	"openness",
	"conscientiousness",
	"extraversion",
	"agreeableness",
	"neuroticism",
	"reasoning_depth",
	"step_by_step",
	"creativity_in_reasoning",
	"synthetics",
	"abstraction",
	"patterns",
	"accuracy",
	"reliability",
	"caution",
	"consistency",
	"self_correction",
	"transparency",
)

PERSONA_MODEL_FIELDS: tuple[str, ...] = (
	*PERSONA_KNOB_FIELDS,
	"model",
	"temperature",
	"max_tokens",
	"system_prompt",
)


class AgentRole(str, Enum):
	ASSISTANT = "assistant"


class MessageRole(str, Enum):
	USER = "user"
	ASSISTANT = "assistant"
	SYSTEM = "system"
	TOOL = "tool"


class PersonaVersionSource(str, Enum):
	MANUAL = "manual"
	PRESET = "preset"
	ANALYSIS = "analysis"
	BLEND = "blend"
	IMPORT = "import"
	CYREX = "cyrex"


class AgentRunStatus(str, Enum):
	PENDING = "pending"
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"
	UNAVAILABLE = "unavailable"


def _score_constraints(*field_names: str) -> list[CheckConstraint]:
	return [CheckConstraint(f"{field_name} >= 0.0 AND {field_name} <= 1.0", name=f"ck_{field_name}_range") for field_name in field_names]


def _enum_constraint(field_name: str, values: tuple[str, ...], *, name: str) -> CheckConstraint:
	allowed = ", ".join(f"'{value}'" for value in values)
	return CheckConstraint(f"{field_name} IN ({allowed})", name=name)


class UUIDPrimaryKeyMixin:
	id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)


class CreatedAtMixin:
	created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UpdatedAtMixin(CreatedAtMixin):
	updated_at: Mapped[datetime] = mapped_column(
		DateTime,
		nullable=False,
		default=datetime.utcnow,
		onupdate=datetime.utcnow,
	)


class PersonaModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "personas"
	__table_args__ = (
		Index("idx_personas_name", "name"),
		Index("idx_personas_is_preset", "is_preset"),
		*_score_constraints(*PERSONA_KNOB_FIELDS),
		CheckConstraint("temperature >= 0.0 AND temperature <= 2.0", name="ck_personas_temperature_range"),
		CheckConstraint("max_tokens >= 1 AND max_tokens <= 32000", name="ck_personas_max_tokens_range"),
	)

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
	system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
	temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
	max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
	is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

	agents: Mapped[list["AgentModel"]] = relationship(back_populates="persona")
	versions: Mapped[list["PersonaVersionModel"]] = relationship(back_populates="persona", cascade="all, delete-orphan")
	analysis_runs: Mapped[list["AnalysisRunModel"]] = relationship(back_populates="persona")

	def knob_values(self) -> dict[str, float]:
		return {field_name: float(getattr(self, field_name)) for field_name in PERSONA_KNOB_FIELDS}

	def settings_values(self) -> dict[str, Any]:
		return {
			"system_prompt": self.system_prompt or "",
			"model": self.model,
			"temperature": self.temperature,
			"max_tokens": self.max_tokens,
		}

	def apply_profile(self, profile: "PersonaProfile") -> None:
		for field_name in PERSONA_KNOB_FIELDS:
			setattr(self, field_name, getattr(profile, field_name))
		self.name = profile.name
		self.description = profile.description
		self.system_prompt = profile.system_prompt
		self.model = profile.model
		self.temperature = profile.temperature
		self.max_tokens = profile.max_tokens

	def to_profile(self) -> "PersonaProfile":
		from ..models import PersonaProfile

		return PersonaProfile(
			id=str(self.id),
			name=self.name,
			description=self.description or "",
			created_at=self.created_at,
			updated_at=self.updated_at,
			system_prompt=self.system_prompt or "",
			**self.knob_values(),
			model=self.model,
			temperature=self.temperature,
			max_tokens=self.max_tokens,
		)

	@classmethod
	def from_profile(cls, profile: "PersonaProfile", *, is_preset: bool = False) -> "PersonaModel":
		model = cls(is_preset=is_preset)
		model.apply_profile(profile)
		return model


class AgentModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "agents"
	__table_args__ = (
		Index("idx_agents_persona_id", "persona_id"),
		CheckConstraint("temperature IS NULL OR (temperature >= 0.0 AND temperature <= 2.0)", name="ck_agents_temperature_range"),
		CheckConstraint("max_tokens IS NULL OR (max_tokens >= 1 AND max_tokens <= 32000)", name="ck_agents_max_tokens_range"),
		_enum_constraint("role", tuple(role.value for role in AgentRole), name="ck_agents_role_values"),
	)

	name: Mapped[str] = mapped_column(String(255), nullable=False)
	role: Mapped[str] = mapped_column(String(100), nullable=False, default=AgentRole.ASSISTANT.value)
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

	persona: Mapped["PersonaModel | None"] = relationship(back_populates="agents")
	sessions: Mapped[list["SessionModel"]] = relationship(back_populates="agent")
	tool_configs: Mapped[list["AgentToolModel"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
	runs: Mapped[list["AgentRunModel"]] = relationship(back_populates="agent", cascade="all, delete-orphan")

	def to_config(self) -> "AgentConfig":
		from ..models import AgentConfig

		return AgentConfig(
			agent_id=str(self.id),
			name=self.name,
			role=self.role,
			model=self.model or "llama3:8b",
			temperature=self.temperature or 0.7,
			max_tokens=self.max_tokens or 2000,
			system_prompt=self.system_prompt or "",
			persona_id=str(self.persona_id) if self.persona_id else None,
			tools=[tool.name for tool in self.tool_configs] or list(self.tools),
			memory_enabled=self.memory_enabled,
			session_id=None,
		)

	@classmethod
	def from_config(cls, config: "AgentConfig") -> "AgentModel":
		return cls(
			name=config.name,
			role=config.role,
			model=config.model,
			temperature=config.temperature,
			max_tokens=config.max_tokens,
			system_prompt=config.system_prompt,
			persona_id=PyUUID(config.persona_id) if config.persona_id else None,
			tools=list(config.tools),
			memory_enabled=config.memory_enabled,
			is_active=True,
		)


class SessionModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "sessions"
	__table_args__ = (
		Index("idx_sessions_agent_id", "agent_id"),
		Index("idx_sessions_session_id", "session_id"),
	)

	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	session_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
	session_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
	message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	agent: Mapped["AgentModel"] = relationship(back_populates="sessions")
	messages: Mapped[list["MessageModel"]] = relationship(back_populates="session")
	runs: Mapped[list["AgentRunModel"]] = relationship(back_populates="session")


class MessageModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "messages"
	__table_args__ = (
		Index("idx_messages_session_id", "session_id"),
		Index("idx_messages_created_at", "created_at"),
		_enum_constraint("role", tuple(role.value for role in MessageRole), name="ck_messages_role_values"),
	)

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

	session: Mapped["SessionModel"] = relationship(back_populates="messages")


class PersonaVersionModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "persona_versions"
	__table_args__ = (
		Index("idx_persona_versions_persona_id", "persona_id"),
		UniqueConstraint("persona_id", "version_number", name="uq_persona_version_number"),
		_enum_constraint("source", tuple(source.value for source in PersonaVersionSource), name="ck_persona_version_source_values"),
	)

	persona_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("personas.id", ondelete="CASCADE"),
		nullable=False,
	)
	version_number: Mapped[int] = mapped_column(Integer, nullable=False)
	source: Mapped[str] = mapped_column(String(50), nullable=False, default=PersonaVersionSource.MANUAL.value)
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	knob_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

	persona: Mapped["PersonaModel"] = relationship(back_populates="versions")


class AgentToolModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "agent_tools"
	__table_args__ = (
		Index("idx_agent_tools_agent_id", "agent_id"),
		UniqueConstraint("agent_id", "name", name="uq_agent_tool_name"),
	)

	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	tool_config: Mapped[dict[str, Any]] = mapped_column("config", JSONB, nullable=False, default=dict)

	agent: Mapped["AgentModel"] = relationship(back_populates="tool_configs")

	@classmethod
	def from_name(cls, *, agent_id: PyUUID, name: str) -> "AgentToolModel":
		return cls(agent_id=agent_id, name=name)


class AnalysisRunModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "analysis_runs"
	__table_args__ = (
		Index("idx_analysis_runs_persona_id", "persona_id"),
		Index("idx_analysis_runs_created_at", "created_at"),
		*_score_constraints("confidence_score"),
	)

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

	persona: Mapped["PersonaModel | None"] = relationship(back_populates="analysis_runs")


class AgentRunModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "agent_runs"
	__table_args__ = (
		Index("idx_agent_runs_agent_id", "agent_id"),
		Index("idx_agent_runs_session_id", "session_id"),
		Index("idx_agent_runs_created_at", "created_at"),
		_enum_constraint("status", tuple(status.value for status in AgentRunStatus), name="ck_agent_runs_status_values"),
	)

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
	status: Mapped[str] = mapped_column(String(30), nullable=False, default=AgentRunStatus.PENDING.value)
	provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
	model: Mapped[str | None] = mapped_column(String(100), nullable=True)
	request_message: Mapped[str] = mapped_column(Text, nullable=False)
	response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
	tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
	run_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
	completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	agent: Mapped["AgentModel"] = relationship(back_populates="runs")
	session: Mapped["SessionModel | None"] = relationship(back_populates="runs")

	def mark_completed(
		self,
		*,
		status: AgentRunStatus,
		response_message: str | None,
		provider: str | None,
		model: str | None,
		tokens_used: int | None = None,
	) -> None:
		self.status = status.value
		self.response_message = response_message
		self.provider = provider
		self.model = model
		self.tokens_used = tokens_used
		self.completed_at = datetime.utcnow()
