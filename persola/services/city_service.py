"""Communal city service — families, lineage spawn, jobs, commons, events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import (
	PERSONA_KNOB_FIELDS,
	AgentModel,
	CityDistrict,
	CityEventModel,
	CityJobModel,
	CityJobStatus,
	FamilyMemberModel,
	FamilyMemberRole,
	FamilyModel,
	PersonaModel,
	WorkspaceArtifactModel,
	WorkspaceRunModel,
	WorkspaceRunStatus,
)
from ..db.repositories import AgentRepository, PersonaRepository
from ..db.repositories.city_repository import (
	CityEventRepository,
	CityJobRepository,
	FamilyMemberRepository,
	FamilyRepository,
	WorkspaceArtifactRepository,
	WorkspaceRunRepository,
)
from ..engine import PersonaEngine

DEFAULT_CITY_TOOL_TAGS: list[str] = ["workspace", "run", "memory", "viz"]

_TOOL_TAG_TO_NAMES: dict[str, list[str]] = {
	"workspace": ["workspace_write", "workspace_read", "workspace_list"],
	"run": ["run_python"],
	"memory": ["memory_store", "memory_recall", "memory_search"],
	"viz": ["emit_viz_event"],
}


def tool_names_for_tags(tags: list[str]) -> list[str]:
	names: list[str] = []
	seen: set[str] = set()
	for tag in tags:
		for name in _TOOL_TAG_TO_NAMES.get(tag, []):
			if name not in seen:
				seen.add(name)
				names.append(name)
	return names


def _clamp_knob(value: float) -> float:
	return max(0.0, min(1.0, float(value)))


class CityService:
	def __init__(self, db: AsyncSession) -> None:
		self.db = db
		self.families = FamilyRepository(db)
		self.members = FamilyMemberRepository(db)
		self.jobs = CityJobRepository(db)
		self.artifacts = WorkspaceArtifactRepository(db)
		self.runs = WorkspaceRunRepository(db)
		self.events = CityEventRepository(db)
		self.agents = AgentRepository(db)
		self.personas = PersonaRepository(db)
		self.engine = PersonaEngine()

	async def emit_event(
		self,
		*,
		event_type: str,
		payload: dict[str, Any] | None = None,
		family_id: UUID | None = None,
		job_id: UUID | None = None,
	) -> CityEventModel:
		event = CityEventModel(
			family_id=family_id,
			job_id=job_id,
			event_type=event_type,
			payload=payload or {},
		)
		return await self.events.create(event)

	def _serialize_member(self, member: FamilyMemberModel) -> dict[str, Any]:
		agent = member.agent
		return {
			"id": str(member.id),
			"family_id": str(member.family_id),
			"agent_id": str(member.agent_id),
			"parent_member_id": str(member.parent_member_id) if member.parent_member_id else None,
			"role_in_family": member.role_in_family,
			"role_label": member.role_label,
			"knob_overrides": member.knob_overrides or {},
			"tool_tags": list(member.tool_tags or []),
			"is_active": member.is_active,
			"agent": {
				"agent_id": str(agent.id),
				"name": agent.name,
				"role": agent.role,
				"persona_id": str(agent.persona_id) if agent.persona_id else None,
				"tools": list(agent.tools or []),
			}
			if agent is not None
			else None,
			"created_at": member.created_at.isoformat() if member.created_at else None,
			"updated_at": member.updated_at.isoformat() if member.updated_at else None,
		}

	def _serialize_family(self, family: FamilyModel, members: list[FamilyMemberModel] | None = None) -> dict[str, Any]:
		member_rows = members if members is not None else list(family.members or [])
		nodes = [self._serialize_member(m) for m in member_rows]
		edges = [
			{"from": str(m.parent_member_id), "to": str(m.id)}
			for m in member_rows
			if m.parent_member_id is not None
		]
		return {
			"id": str(family.id),
			"name": family.name,
			"description": family.description,
			"default_district": family.default_district,
			"policy": family.policy or {},
			"is_active": family.is_active,
			"members": nodes,
			"lineage": {"nodes": nodes, "edges": edges},
			"created_at": family.created_at.isoformat() if family.created_at else None,
			"updated_at": family.updated_at.isoformat() if family.updated_at else None,
		}

	def _serialize_job(self, job: CityJobModel) -> dict[str, Any]:
		return {
			"id": str(job.id),
			"family_id": str(job.family_id),
			"goal": job.goal,
			"district": job.district,
			"status": job.status,
			"result_summary": job.result_summary,
			"result": job.result or {},
			"team_session_id": str(job.team_session_id) if job.team_session_id else None,
			"created_at": job.created_at.isoformat() if job.created_at else None,
			"updated_at": job.updated_at.isoformat() if job.updated_at else None,
			"completed_at": job.completed_at.isoformat() if job.completed_at else None,
		}

	@staticmethod
	def _serialize_artifact(row: WorkspaceArtifactModel) -> dict[str, Any]:
		return {
			"id": str(row.id),
			"job_id": str(row.job_id),
			"family_id": str(row.family_id),
			"path": row.path,
			"content": row.content,
			"content_type": row.content_type,
			"size_bytes": row.size_bytes,
			"version": row.version,
			"created_by_agent_id": str(row.created_by_agent_id) if row.created_by_agent_id else None,
			"metadata": row.artifact_metadata or {},
			"created_at": row.created_at.isoformat() if row.created_at else None,
		}

	@staticmethod
	def _serialize_run(row: WorkspaceRunModel) -> dict[str, Any]:
		return {
			"id": str(row.id),
			"job_id": str(row.job_id),
			"tool": row.tool,
			"args": row.args or {},
			"status": row.status,
			"stdout": row.stdout,
			"stderr": row.stderr,
			"duration_ms": row.duration_ms,
			"started_by_agent_id": str(row.started_by_agent_id) if row.started_by_agent_id else None,
			"artifact_refs": list(row.artifact_refs or []),
			"created_at": row.created_at.isoformat() if row.created_at else None,
			"completed_at": row.completed_at.isoformat() if row.completed_at else None,
		}

	@staticmethod
	def _serialize_event(row: CityEventModel) -> dict[str, Any]:
		return {
			"id": str(row.id),
			"family_id": str(row.family_id) if row.family_id else None,
			"job_id": str(row.job_id) if row.job_id else None,
			"event_type": row.event_type,
			"payload": row.payload or {},
			"created_at": row.created_at.isoformat() if row.created_at else None,
		}

	async def list_families(self, limit: int = 50) -> list[dict[str, Any]]:
		rows = await self.families.list_recent(limit=limit)
		return [
			{
				"id": str(f.id),
				"name": f.name,
				"description": f.description,
				"default_district": f.default_district,
				"is_active": f.is_active,
				"created_at": f.created_at.isoformat() if f.created_at else None,
				"updated_at": f.updated_at.isoformat() if f.updated_at else None,
			}
			for f in rows
		]

	async def get_family(self, family_id: UUID) -> dict[str, Any] | None:
		family = await self.families.get_with_members(family_id)
		if family is None:
			return None
		return self._serialize_family(family)

	async def create_family(
		self,
		*,
		name: str,
		description: str | None = None,
		default_district: str = CityDistrict.BUILD.value,
		policy: dict[str, Any] | None = None,
		parent_agent_id: UUID | None = None,
		parent_name: str | None = None,
		persona_id: UUID | None = None,
		tool_tags: list[str] | None = None,
		role_label: str | None = "coordinator",
	) -> dict[str, Any]:
		if default_district not in {d.value for d in CityDistrict}:
			raise ValueError(f"Invalid district: {default_district}")

		tags = list(tool_tags) if tool_tags is not None else list(DEFAULT_CITY_TOOL_TAGS)
		parent_agent: AgentModel | None = None

		if parent_agent_id is not None:
			parent_agent = await self.agents.get(parent_agent_id)
			if parent_agent is None:
				raise ValueError("parent_agent_id not found")
		else:
			resolved_persona_id = persona_id
			if resolved_persona_id is None:
				persona = await self.personas.create(
					PersonaModel(
						name=f"{name} Parent Persona",
						description=description or f"Parent persona for family {name}",
					)
				)
				resolved_persona_id = persona.id
			else:
				persona = await self.personas.get(resolved_persona_id)
				if persona is None:
					raise ValueError("persona_id not found")

			profile = persona.to_profile()
			parent_agent = await self.agents.create(
				AgentModel(
					name=parent_name or f"{name} Parent",
					role="assistant",
					persona_id=resolved_persona_id,
					system_prompt=self.engine.build_system_prompt(profile),
					tools=tool_names_for_tags(tags),
					memory_enabled=True,
					is_active=True,
				)
			)

		family = await self.families.create(
			FamilyModel(
				name=name,
				description=description,
				default_district=default_district,
				policy=policy or {},
				is_active=True,
			)
		)

		parent_member = await self.members.create(
			FamilyMemberModel(
				family_id=family.id,
				agent_id=parent_agent.id,
				parent_member_id=None,
				role_in_family=FamilyMemberRole.PARENT.value,
				role_label=role_label,
				knob_overrides={},
				tool_tags=tags,
				is_active=True,
			)
		)

		await self.emit_event(
			event_type="family.created",
			family_id=family.id,
			payload={
				"family_id": str(family.id),
				"name": family.name,
				"parent_member_id": str(parent_member.id),
				"parent_agent_id": str(parent_agent.id),
			},
		)
		await self.emit_event(
			event_type="agent.spawned",
			family_id=family.id,
			payload={
				"family_id": str(family.id),
				"member_id": str(parent_member.id),
				"agent_id": str(parent_agent.id),
				"parent_id": None,
				"role": FamilyMemberRole.PARENT.value,
				"role_label": role_label,
			},
		)

		await self.db.commit()
		detail = await self.get_family(family.id)
		assert detail is not None
		return detail

	async def spawn_child(
		self,
		family_id: UUID,
		*,
		name: str,
		knob_overrides: dict[str, float] | None = None,
		tool_tags: list[str] | None = None,
		role_label: str | None = None,
		parent_member_id: UUID | None = None,
		description: str | None = None,
	) -> dict[str, Any]:
		family = await self.families.get_with_members(family_id)
		if family is None:
			raise ValueError("Family not found")

		if parent_member_id is not None:
			parent_member = next((m for m in family.members if m.id == parent_member_id), None)
			if parent_member is None:
				raise ValueError("parent_member_id not in family")
		else:
			parent_member = await self.members.get_parent(family_id)
			if parent_member is None:
				raise ValueError("Family has no parent member")

		parent_agent = await self.agents.get(parent_member.agent_id)
		if parent_agent is None:
			raise ValueError("Parent agent missing")

		overrides = {k: _clamp_knob(v) for k, v in (knob_overrides or {}).items() if k in PERSONA_KNOB_FIELDS}
		inherited_tags = list(tool_tags) if tool_tags is not None else list(parent_member.tool_tags or DEFAULT_CITY_TOOL_TAGS)

		base_knobs: dict[str, float] = {}
		parent_persona: PersonaModel | None = None
		if parent_agent.persona_id:
			parent_persona = await self.personas.get(parent_agent.persona_id)
			if parent_persona is not None:
				base_knobs = parent_persona.knob_values()

		merged_knobs = {**base_knobs, **overrides}
		child_persona = await self.personas.create(
			PersonaModel(
				name=f"{name} Persona",
				description=description or f"Child of {parent_agent.name} in family {family.name}",
				**{field: merged_knobs.get(field, 0.5) for field in PERSONA_KNOB_FIELDS},
				model=parent_persona.model if parent_persona else "llama3:8b",
				temperature=parent_persona.temperature if parent_persona else 0.7,
				max_tokens=parent_persona.max_tokens if parent_persona else 2000,
			)
		)
		profile = child_persona.to_profile()
		child_agent = await self.agents.create(
			AgentModel(
				name=name,
				role="assistant",
				persona_id=child_persona.id,
				system_prompt=self.engine.build_system_prompt(profile),
				tools=tool_names_for_tags(inherited_tags),
				memory_enabled=True,
				is_active=True,
			)
		)

		child_member = await self.members.create(
			FamilyMemberModel(
				family_id=family.id,
				agent_id=child_agent.id,
				parent_member_id=parent_member.id,
				role_in_family=FamilyMemberRole.CHILD.value,
				role_label=role_label,
				knob_overrides=overrides,
				tool_tags=inherited_tags,
				is_active=True,
			)
		)

		await self.emit_event(
			event_type="agent.spawned",
			family_id=family.id,
			payload={
				"family_id": str(family.id),
				"member_id": str(child_member.id),
				"agent_id": str(child_agent.id),
				"parent_id": str(parent_member.id),
				"parent_agent_id": str(parent_agent.id),
				"role": FamilyMemberRole.CHILD.value,
				"role_label": role_label,
				"knob_overrides": overrides,
				"tool_tags": inherited_tags,
			},
		)

		await self.db.commit()
		members = await self.members.list_for_family(family_id)
		child = next((m for m in members if m.id == child_member.id), None)
		if child is None:
			raise ValueError("Spawned child member missing after commit")
		return self._serialize_member(child)

	async def start_job(
		self,
		*,
		family_id: UUID,
		goal: str,
		district: str | None = None,
		team_session_id: UUID | None = None,
		status: str = CityJobStatus.PENDING.value,
	) -> dict[str, Any]:
		family = await self.families.get(family_id)
		if family is None:
			raise ValueError("Family not found")

		resolved_district = district or family.default_district
		if resolved_district not in {d.value for d in CityDistrict}:
			raise ValueError(f"Invalid district: {resolved_district}")
		if status not in {s.value for s in CityJobStatus}:
			raise ValueError(f"Invalid status: {status}")

		job = await self.jobs.create(
			CityJobModel(
				family_id=family_id,
				goal=goal,
				district=resolved_district,
				status=status,
				result={},
				team_session_id=team_session_id,
			)
		)

		await self.emit_event(
			event_type="job.started",
			family_id=family_id,
			job_id=job.id,
			payload={
				"job_id": str(job.id),
				"family_id": str(family_id),
				"goal": goal,
				"district": resolved_district,
				"status": status,
			},
		)

		await self.db.commit()
		await self.db.refresh(job)
		return self._serialize_job(job)

	async def get_job(self, job_id: UUID) -> dict[str, Any] | None:
		job = await self.jobs.get(job_id)
		if job is None:
			return None
		payload = self._serialize_job(job)
		payload["artifact_count"] = len(await self.artifacts.list_for_job(job_id, limit=1000))
		payload["run_count"] = len(await self.runs.list_for_job(job_id, limit=1000))
		payload["event_count"] = len(await self.events.list_for_job(job_id, limit=1000))
		return payload

	async def list_artifacts(self, job_id: UUID, limit: int = 200) -> list[dict[str, Any]]:
		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		rows = await self.artifacts.list_for_job(job_id, limit=limit)
		return [self._serialize_artifact(r) for r in rows]

	async def list_runs(self, job_id: UUID, limit: int = 200) -> list[dict[str, Any]]:
		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		rows = await self.runs.list_for_job(job_id, limit=limit)
		return [self._serialize_run(r) for r in rows]

	async def list_events(
		self,
		*,
		job_id: UUID | None = None,
		family_id: UUID | None = None,
		limit: int = 500,
	) -> list[dict[str, Any]]:
		if job_id is not None:
			job = await self.jobs.get(job_id)
			if job is None:
				raise ValueError("Job not found")
			rows = await self.events.list_for_job(job_id, limit=limit)
		elif family_id is not None:
			family = await self.families.get(family_id)
			if family is None:
				raise ValueError("Family not found")
			rows = await self.events.list_for_family(family_id, limit=limit)
		else:
			raise ValueError("job_id or family_id required")
		return [self._serialize_event(r) for r in rows]

	# ── Commons helpers for Phase 2 (usable now for persistence tests) ──

	async def record_artifact(
		self,
		*,
		job_id: UUID,
		path: str,
		content: str | None,
		created_by_agent_id: UUID | None = None,
		content_type: str = "text/plain",
		metadata: dict[str, Any] | None = None,
		commit: bool = True,
	) -> dict[str, Any]:
		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")

		version = (await self.artifacts.latest_version(job_id, path)) + 1
		body = content or ""
		row = await self.artifacts.create(
			WorkspaceArtifactModel(
				job_id=job_id,
				family_id=job.family_id,
				path=path,
				content=content,
				content_type=content_type,
				size_bytes=len(body.encode("utf-8")),
				version=version,
				created_by_agent_id=created_by_agent_id,
				artifact_metadata=metadata or {},
			)
		)
		await self.emit_event(
			event_type="artifact.written",
			family_id=job.family_id,
			job_id=job_id,
			payload={
				"artifact_id": str(row.id),
				"path": path,
				"version": version,
				"size_bytes": row.size_bytes,
				"agent_id": str(created_by_agent_id) if created_by_agent_id else None,
				"job_id": str(job_id),
			},
		)
		if commit:
			await self.db.commit()
			await self.db.refresh(row)
		return self._serialize_artifact(row)

	async def record_run(
		self,
		*,
		job_id: UUID,
		tool: str,
		args: dict[str, Any] | None = None,
		status: str = WorkspaceRunStatus.PENDING.value,
		stdout: str | None = None,
		stderr: str | None = None,
		duration_ms: int | None = None,
		started_by_agent_id: UUID | None = None,
		artifact_refs: list[Any] | None = None,
		commit: bool = True,
	) -> dict[str, Any]:
		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		if status not in {s.value for s in WorkspaceRunStatus}:
			raise ValueError(f"Invalid run status: {status}")

		row = await self.runs.create(
			WorkspaceRunModel(
				job_id=job_id,
				tool=tool,
				args=args or {},
				status=status,
				stdout=stdout,
				stderr=stderr,
				duration_ms=duration_ms,
				started_by_agent_id=started_by_agent_id,
				artifact_refs=artifact_refs or [],
			)
		)
		await self.emit_event(
			event_type="run.finished" if status != WorkspaceRunStatus.PENDING.value else "run.started",
			family_id=job.family_id,
			job_id=job_id,
			payload={
				"run_id": str(row.id),
				"tool": tool,
				"status": status,
				"duration_ms": duration_ms,
				"agent_id": str(started_by_agent_id) if started_by_agent_id else None,
				"job_id": str(job_id),
			},
		)
		if commit:
			await self.db.commit()
			await self.db.refresh(row)
		return self._serialize_run(row)
