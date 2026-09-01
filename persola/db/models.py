from __future__ import annotations

from datetime import datetime, timezone
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


class WorkTaskStatus(str, Enum):
	QUEUED = "queued"
	CLAIMED = "claimed"
	IN_PROGRESS = "in_progress"
	BLOCKED = "blocked"
	DONE = "done"
	FAILED = "failed"


class AuditEventType(str, Enum):
	INSTRUCTION = "instruction"
	DECISION = "decision"
	REPLY = "reply"
	STATUS_CHANGE = "status_change"
	TOOL_CALL = "tool_call"


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


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


# Sentinel tenant used as the default for legacy / un-scoped rows and for the
# system pre-seeded presets. Payloads created without an explicit tenant land
# here rather than failing, preserving backward compatibility.
DEFAULT_TENANT = PyUUID("00000000-0000-0000-0000-000000000000")


class TenantMixin:
    """Adds a tenant_id column used to scope rows to an owning tenant."""

    tenant_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=DEFAULT_TENANT,
        index=True,
    )


class PersonaModel(UUIDPrimaryKeyMixin, TenantMixin, UpdatedAtMixin, Base):
	__tablename__ = "personas"
	__table_args__ = (
		Index("idx_personas_name", "name"),
		Index("idx_personas_is_preset", "is_preset"),
		UniqueConstraint("tenant_id", "name", name="uq_personas_tenant_name"),
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


class AgentModel(UUIDPrimaryKeyMixin, TenantMixin, UpdatedAtMixin, Base):
	__tablename__ = "agents"
	__table_args__ = (
		Index("idx_agents_persona_id", "persona_id"),
		UniqueConstraint("tenant_id", "name", name="uq_agents_tenant_name"),
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

		# Prefer JSON tools column; avoid lazy-loading tool_configs (async-safe).
		tools = list(self.tools or [])
		return AgentConfig(
			agent_id=str(self.id),
			name=self.name,
			role=self.role,
			model=self.model or "llama3:8b",
			temperature=self.temperature or 0.7,
			max_tokens=self.max_tokens or 2000,
			system_prompt=self.system_prompt or "",
			persona_id=str(self.persona_id) if self.persona_id else None,
			tools=tools,
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


class SessionModel(UUIDPrimaryKeyMixin, TenantMixin, CreatedAtMixin, Base):
	__tablename__ = "sessions"
	__table_args__ = (
		Index("idx_sessions_agent_id", "agent_id"),
		Index("idx_sessions_session_id", "session_id"),
		UniqueConstraint("tenant_id", "session_id", name="uq_sessions_tenant_session_id"),
	)

	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	session_id: Mapped[str] = mapped_column(String(100), nullable=False)
	session_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
	message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	agent: Mapped["AgentModel"] = relationship(back_populates="sessions")
	messages: Mapped[list["MessageModel"]] = relationship(back_populates="session")
	runs: Mapped[list["AgentRunModel"]] = relationship(back_populates="session")


class MessageModel(UUIDPrimaryKeyMixin, TenantMixin, CreatedAtMixin, Base):
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


class AnalysisRunModel(UUIDPrimaryKeyMixin, TenantMixin, CreatedAtMixin, Base):
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


class AgentRunModel(UUIDPrimaryKeyMixin, TenantMixin, CreatedAtMixin, Base):
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


class TeamWorkflowStatus(str, Enum):
	PENDING = "pending"
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"


class TeamSessionModel(UUIDPrimaryKeyMixin, TenantMixin, UpdatedAtMixin, Base):
	__tablename__ = "team_sessions"
	__table_args__ = (
		Index("idx_team_sessions_external_id", "external_session_id"),
		UniqueConstraint("tenant_id", "external_session_id", name="uq_team_sessions_tenant_external_id"),
	)

	external_session_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
	name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	persona_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("personas.id", ondelete="SET NULL"),
		nullable=True,
	)
	team_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	memory_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

	workflows: Mapped[list["TeamWorkflowModel"]] = relationship(back_populates="team_session", cascade="all, delete-orphan")
	memory_entries: Mapped[list["TeamMemoryModel"]] = relationship(back_populates="team_session", cascade="all, delete-orphan")


class TeamWorkflowModel(UUIDPrimaryKeyMixin, TenantMixin, CreatedAtMixin, Base):
	__tablename__ = "team_workflows"
	__table_args__ = (
		Index("idx_team_workflows_session_id", "team_session_id"),
		Index("idx_team_workflows_status", "status"),
		_enum_constraint("status", tuple(s.value for s in TeamWorkflowStatus), name="ck_team_workflows_status_values"),
	)

	team_session_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("team_sessions.id", ondelete="CASCADE"),
		nullable=False,
	)
	goal: Mapped[str] = mapped_column(Text, nullable=False)
	status: Mapped[str] = mapped_column(String(30), nullable=False, default=TeamWorkflowStatus.PENDING.value)
	delegation_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
	personalities_used: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
	tool_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
	completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	team_session: Mapped["TeamSessionModel"] = relationship(back_populates="workflows")
	steps: Mapped[list["TeamWorkflowStepModel"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class TeamWorkflowStepModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "team_workflow_steps"
	__table_args__ = (Index("idx_team_workflow_steps_workflow_id", "workflow_id"),)

	workflow_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("team_workflows.id", ondelete="CASCADE"),
		nullable=False,
	)
	step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	role: Mapped[str] = mapped_column(String(50), nullable=False)
	task: Mapped[str] = mapped_column(Text, nullable=False)
	output: Mapped[str] = mapped_column(Text, nullable=False, default="")
	tool_calls: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
	parallel_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
	duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

	workflow: Mapped["TeamWorkflowModel"] = relationship(back_populates="steps")


class TeamMemoryModel(UUIDPrimaryKeyMixin, TenantMixin, CreatedAtMixin, Base):
	__tablename__ = "team_memory"
	__table_args__ = (
		Index("idx_team_memory_session_id", "team_session_id"),
		Index("idx_team_memory_key", "memory_key"),
	)

	team_session_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("team_sessions.id", ondelete="CASCADE"),
		nullable=False,
	)
	memory_key: Mapped[str] = mapped_column(String(255), nullable=False)
	value: Mapped[str] = mapped_column(Text, nullable=False)
	tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
	source_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

	team_session: Mapped["TeamSessionModel"] = relationship(back_populates="memory_entries")


# ── Communal City (Phase 1) ─────────────────────────────────────────────────


class FamilyMemberRole(str, Enum):
	PARENT = "parent"
	CHILD = "child"


class FamilyMemberLifeStatus(str, Enum):
	ALIVE = "alive"
	DECEASED = "deceased"


class CityDistrict(str, Enum):
	BUILD = "build"
	VIZ = "viz"
	RESEARCH = "research"
	OPS = "ops"


class CityJobStatus(str, Enum):
	PENDING = "pending"
	PLANNED = "planned"
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"


class WorkspaceRunStatus(str, Enum):
	PENDING = "pending"
	RUNNING = "running"
	SUCCEEDED = "succeeded"
	FAILED = "failed"
	TIMEOUT = "timeout"
	DENIED = "denied"


class FamilyModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "families"
	__table_args__ = (
		Index("idx_families_name", "name"),
		_enum_constraint("default_district", tuple(d.value for d in CityDistrict), name="ck_families_default_district"),
	)

	name: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	default_district: Mapped[str] = mapped_column(String(30), nullable=False, default=CityDistrict.BUILD.value)
	policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

	members: Mapped[list["FamilyMemberModel"]] = relationship(
		back_populates="family",
		cascade="all, delete-orphan",
	)
	jobs: Mapped[list["CityJobModel"]] = relationship(back_populates="family", cascade="all, delete-orphan")
	artifacts: Mapped[list["WorkspaceArtifactModel"]] = relationship(
		back_populates="family",
		cascade="all, delete-orphan",
	)
	events: Mapped[list["CityEventModel"]] = relationship(back_populates="family", cascade="all, delete-orphan")


class FamilyMemberModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "family_members"
	__table_args__ = (
		Index("idx_family_members_family_id", "family_id"),
		Index("idx_family_members_agent_id", "agent_id"),
		Index("idx_family_members_life_status", "life_status"),
		Index("idx_family_members_generation", "generation"),
		UniqueConstraint("family_id", "agent_id", name="uq_family_member_agent"),
		_enum_constraint("role_in_family", tuple(r.value for r in FamilyMemberRole), name="ck_family_members_role"),
		_enum_constraint(
			"life_status",
			tuple(s.value for s in FamilyMemberLifeStatus),
			name="ck_family_members_life_status",
		),
	)

	family_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("families.id", ondelete="CASCADE"),
		nullable=False,
	)
	agent_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="CASCADE"),
		nullable=False,
	)
	parent_member_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("family_members.id", ondelete="SET NULL"),
		nullable=True,
	)
	role_in_family: Mapped[str] = mapped_column(String(20), nullable=False, default=FamilyMemberRole.CHILD.value)
	role_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
	knob_overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	tool_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	age_ticks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	max_age_ticks: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
	life_status: Mapped[str] = mapped_column(
		String(20),
		nullable=False,
		default=FamilyMemberLifeStatus.ALIVE.value,
	)
	goals: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
	dreams: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
	structured_thinking: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
	growth: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
	deceased_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
	successor_of_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("family_members.id", ondelete="SET NULL"),
		nullable=True,
	)
	legacy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

	family: Mapped["FamilyModel"] = relationship(back_populates="members")
	agent: Mapped["AgentModel"] = relationship()
	parent_member: Mapped["FamilyMemberModel | None"] = relationship(
		remote_side="FamilyMemberModel.id",
		foreign_keys=[parent_member_id],
	)


class CityJobModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "city_jobs"
	__table_args__ = (
		Index("idx_city_jobs_family_id", "family_id"),
		Index("idx_city_jobs_status", "status"),
		_enum_constraint("district", tuple(d.value for d in CityDistrict), name="ck_city_jobs_district"),
		_enum_constraint("status", tuple(s.value for s in CityJobStatus), name="ck_city_jobs_status"),
	)

	family_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("families.id", ondelete="CASCADE"),
		nullable=False,
	)
	goal: Mapped[str] = mapped_column(Text, nullable=False)
	district: Mapped[str] = mapped_column(String(30), nullable=False, default=CityDistrict.BUILD.value)
	status: Mapped[str] = mapped_column(String(30), nullable=False, default=CityJobStatus.PENDING.value)
	result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	team_session_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("team_sessions.id", ondelete="SET NULL"),
		nullable=True,
	)
	completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	family: Mapped["FamilyModel"] = relationship(back_populates="jobs")
	artifacts: Mapped[list["WorkspaceArtifactModel"]] = relationship(
		back_populates="job",
		cascade="all, delete-orphan",
	)
	runs: Mapped[list["WorkspaceRunModel"]] = relationship(back_populates="job", cascade="all, delete-orphan")
	events: Mapped[list["CityEventModel"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class WorkspaceArtifactModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "workspace_artifacts"
	__table_args__ = (
		Index("idx_workspace_artifacts_job_id", "job_id"),
		Index("idx_workspace_artifacts_family_id", "family_id"),
		Index("idx_workspace_artifacts_path", "path"),
		UniqueConstraint("job_id", "path", "version", name="uq_workspace_artifact_path_version"),
	)

	job_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("city_jobs.id", ondelete="CASCADE"),
		nullable=False,
	)
	family_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("families.id", ondelete="CASCADE"),
		nullable=False,
	)
	path: Mapped[str] = mapped_column(String(512), nullable=False)
	content: Mapped[str | None] = mapped_column(Text, nullable=True)
	content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="text/plain")
	size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
	created_by_agent_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="SET NULL"),
		nullable=True,
	)
	artifact_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)

	job: Mapped["CityJobModel"] = relationship(back_populates="artifacts")
	family: Mapped["FamilyModel"] = relationship(back_populates="artifacts")


class WorkspaceRunModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "workspace_runs"
	__table_args__ = (
		Index("idx_workspace_runs_job_id", "job_id"),
		Index("idx_workspace_runs_status", "status"),
		_enum_constraint("status", tuple(s.value for s in WorkspaceRunStatus), name="ck_workspace_runs_status"),
	)

	job_id: Mapped[PyUUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("city_jobs.id", ondelete="CASCADE"),
		nullable=False,
	)
	tool: Mapped[str] = mapped_column(String(100), nullable=False)
	args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	status: Mapped[str] = mapped_column(String(30), nullable=False, default=WorkspaceRunStatus.PENDING.value)
	stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
	stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
	duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
	started_by_agent_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("agents.id", ondelete="SET NULL"),
		nullable=True,
	)
	artifact_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
	completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

	job: Mapped["CityJobModel"] = relationship(back_populates="runs")


class CityEventModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
	__tablename__ = "city_events"
	__table_args__ = (
		Index("idx_city_events_job_id", "job_id"),
		Index("idx_city_events_family_id", "family_id"),
		Index("idx_city_events_type", "event_type"),
		Index("idx_city_events_created_at", "created_at"),
	)

	family_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("families.id", ondelete="CASCADE"),
		nullable=True,
	)
	job_id: Mapped[PyUUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("city_jobs.id", ondelete="CASCADE"),
		nullable=True,
	)
	event_type: Mapped[str] = mapped_column(String(80), nullable=False)
	payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

	family: Mapped["FamilyModel | None"] = relationship(back_populates="events")
	job: Mapped["CityJobModel | None"] = relationship(back_populates="events")


class OrgNodeModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
	__tablename__ = "org_nodes"
	__table_args__ = (
		Index("idx_org_nodes_team_id", "team_id"),
		UniqueConstraint("team_id", "role", name="uq_org_node_team_role"),
	)

	team_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
	role: Mapped[str] = mapped_column(String(100), nullable=False)
	title: Mapped[str] = mapped_column(String(255), nullable=False)
	reports_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
	email: Mapped[str | None] = mapped_column(String(255), nullable=True)
	active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class WorkTaskModel(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "work_tasks"
	__table_args__ = (
		Index("idx_work_tasks_team_id", "team_id"),
		Index("idx_work_tasks_status", "status"),
		Index("idx_work_tasks_role", "role"),
		Index("idx_work_tasks_created_at", "created_at"),
		UniqueConstraint("task_id", name="uq_work_tasks_task_id"),
		_enum_constraint("status", tuple(s.value for s in WorkTaskStatus), name="ck_work_tasks_status"),
	)

	task_id: Mapped[str] = mapped_column(String(100), nullable=False)
	team_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
	role: Mapped[str] = mapped_column(String(100), nullable=False, default="coordinator")
	subtask: Mapped[str] = mapped_column(Text, nullable=False)
	origin: Mapped[str] = mapped_column(String(100), nullable=False, default="user")
	status: Mapped[str] = mapped_column(String(30), nullable=False, default=WorkTaskStatus.QUEUED.value)
	result: Mapped[str | None] = mapped_column(Text, nullable=True)
	error: Mapped[str | None] = mapped_column(Text, nullable=True)
	parent_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
	session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
	claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEventModel(UUIDPrimaryKeyMixin, Base):
	__tablename__ = "audit_events"
	__table_args__ = (
		Index("idx_audit_events_team_id", "team_id"),
		Index("idx_audit_events_session_id", "session_id"),
		Index("idx_audit_events_task_id", "task_id"),
		Index("idx_audit_events_created_at", "created_at"),
		UniqueConstraint("event_id", name="uq_audit_events_event_id"),
		_enum_constraint("event_type", tuple(t.value for t in AuditEventType), name="ck_audit_events_type"),
	)

	event_id: Mapped[str] = mapped_column(String(100), nullable=False)
	team_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
	session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
	task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
	event_type: Mapped[str] = mapped_column(String(30), nullable=False, default=AuditEventType.INSTRUCTION.value)
	actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
	recipient: Mapped[str | None] = mapped_column(String(100), nullable=True)
	summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
	detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
