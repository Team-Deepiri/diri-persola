"""Communal city service — families, lineage spawn, jobs, commons, events."""

from __future__ import annotations

from datetime import datetime
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
from ..orchestration.city_scale import DEFAULT_SCALE_CONFIG

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
		self.model_tiers = DEFAULT_SCALE_CONFIG.model_tiers

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
			parent_model = self.model_tiers.for_role("parent", role_label)
			persona.model = parent_model
			await self.db.flush()
			parent_agent = await self.agents.create(
				AgentModel(
					name=parent_name or f"{name} Parent",
					role="assistant",
					persona_id=resolved_persona_id,
					model=parent_model,
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
		child_model = self.model_tiers.for_role("child", role_label)
		child_persona = await self.personas.create(
			PersonaModel(
				name=f"{name} Persona",
				description=description or f"Child of {parent_agent.name} in family {family.name}",
				**{field: merged_knobs.get(field, 0.5) for field in PERSONA_KNOB_FIELDS},
				model=child_model,
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
				model=child_model,
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

		try:
			from ..metrics import record_city_job

			record_city_job(resolved_district, status)
		except Exception:
			pass

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

	async def get_artifact_by_path(self, job_id: UUID, path: str) -> dict[str, Any] | None:
		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		row = await self.artifacts.get_latest_by_path(job_id, path)
		if row is None:
			return None
		return self._serialize_artifact(row)

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

	async def list_events_since(
		self,
		*,
		family_id: UUID | None = None,
		job_id: UUID | None = None,
		after_id: UUID | None = None,
		since: datetime | None = None,
		limit: int = 100,
	) -> list[dict[str, Any]]:
		"""Incremental event fetch for SSE / polling (Austin live stream)."""
		if family_id is None and job_id is None:
			raise ValueError("family_id or job_id required")
		if family_id is not None and await self.families.get(family_id) is None:
			raise ValueError("Family not found")
		if job_id is not None and await self.jobs.get(job_id) is None:
			raise ValueError("Job not found")
		rows = await self.events.list_since(
			family_id=family_id,
			job_id=job_id,
			after_id=after_id,
			since=since,
			limit=limit,
		)
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
		try:
			from ..metrics import record_city_tool_run

			record_city_tool_run(tool, status)
		except Exception:
			pass
		return self._serialize_run(row)

	async def set_job_status(
		self,
		job_id: UUID,
		*,
		status: str,
		result_summary: str | None = None,
		result: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		from datetime import datetime

		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		if status not in {s.value for s in CityJobStatus}:
			raise ValueError(f"Invalid status: {status}")
		job.status = status
		if result_summary is not None:
			job.result_summary = result_summary
		if result is not None:
			job.result = result
		if status in {CityJobStatus.COMPLETED.value, CityJobStatus.FAILED.value}:
			job.completed_at = datetime.utcnow()
			await self.emit_event(
				event_type="job.completed",
				family_id=job.family_id,
				job_id=job.id,
				payload={
					"job_id": str(job.id),
					"family_id": str(job.family_id),
					"status": status,
					"result_summary": result_summary,
				},
			)
		await self.db.commit()
		await self.db.refresh(job)
		try:
			from ..metrics import record_city_job, set_city_cohesion_score

			record_city_job(job.district, status)
			if status == CityJobStatus.COMPLETED.value:
				score = await self.cohesion_score(job.id)
				set_city_cohesion_score(score["score"])
		except Exception:
			pass
		return self._serialize_job(job)

	async def execute_tool_calls(
		self,
		job_id: UUID,
		calls: list[dict[str, Any]],
		*,
		agent_id: UUID | None = None,
		session_id: str | None = None,
		governed: bool = True,
	) -> dict[str, Any]:
		"""Run structured tool calls against the city commons registry."""
		from ..orchestration.city_scale import GLOBAL_GOVERNOR
		from ..orchestration.city_tools import build_city_registry
		from ..orchestration.tool_calls import parse_tool_calls

		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")

		if job.status == CityJobStatus.PENDING.value:
			job.status = CityJobStatus.RUNNING.value
			await self.db.flush()

		acquired = False
		if governed:
			await GLOBAL_GOVERNOR.acquire(
				family_id=str(job.family_id),
				district=job.district,
				job_id=str(job.id),
			)
			acquired = True

		try:
			registry = await build_city_registry(
				session_id or f"city-job-{job_id}",
				db=self.db,
				job_id=job_id,
				agent_id=agent_id,
			)

			normalized: list[dict[str, Any]] = []
			for call in calls:
				if isinstance(call, str):
					normalized.extend(parse_tool_calls(call))
				elif isinstance(call, dict):
					name = call.get("name")
					if not name:
						continue
					args = call.get("args") or call.get("arguments") or {}
					normalized.append({"name": str(name), "args": args if isinstance(args, dict) else {}})

			results: list[dict[str, Any]] = []
			for call in normalized:
				name = call["name"]
				args = call.get("args") or {}
				try:
					result = await registry.run(name, **args)
					ok = bool(result.get("ok")) if "ok" in result else not bool(result.get("error"))
					results.append({"name": name, "args": args, "result": result, "ok": ok})
				except Exception as exc:  # noqa: BLE001 — surface tool failures to caller
					results.append({"name": name, "args": args, "error": str(exc), "ok": False})

			await self.db.commit()
			fresh = await self.jobs.get(job_id)
			return {
				"job_id": str(job_id),
				"status": fresh.status if fresh else job.status,
				"tool_results": results,
			}
		finally:
			if acquired:
				GLOBAL_GOVERNOR.release(
					family_id=str(job.family_id),
					district=job.district,
					job_id=str(job.id),
				)

	# ── Phase 3 wedge demo ───────────────────────────────────────────────

	WEDGE_CHILDREN: tuple[dict[str, Any], ...] = (
		{
			"name": "Nova Analyst",
			"role_label": "analyst",
			"knob_overrides": {"reasoning_depth": 0.95, "accuracy": 0.95, "creativity": 0.35},
		},
		{
			"name": "Lux Creative",
			"role_label": "creative",
			"knob_overrides": {"creativity": 0.95, "humor": 0.7, "openness": 0.9},
		},
		{
			"name": "Forge Executor",
			"role_label": "executor",
			"knob_overrides": {"conscientiousness": 0.9, "step_by_step": 0.9, "reliability": 0.95},
		},
		{
			"name": "Kai Empath",
			"role_label": "empath",
			"knob_overrides": {"empathy": 0.95, "agreeableness": 0.9, "verbosity": 0.55},
		},
		{
			"name": "Atlas Builder",
			"role_label": "builder",
			"knob_overrides": {"patterns": 0.85, "synthetics": 0.8, "accuracy": 0.85},
		},
	)

	async def seed_wedge_family(self, *, name: str = "Wedge City Family") -> dict[str, Any]:
		"""Create a parent + 5 distinct children for the Phase 3 demo."""
		family = await self.create_family(
			name=name,
			description="Phase 3 wedge demo family — shared commons, build and run.",
			default_district=CityDistrict.BUILD.value,
			parent_name="Orion Coordinator",
			role_label="coordinator",
			tool_tags=list(DEFAULT_CITY_TOOL_TAGS),
			policy={"wedge": True, "max_children": 8},
		)
		family_id = UUID(family["id"])
		for child in self.WEDGE_CHILDREN:
			await self.spawn_child(
				family_id,
				name=str(child["name"]),
				role_label=str(child["role_label"]),
				knob_overrides=dict(child.get("knob_overrides") or {}),
				tool_tags=list(DEFAULT_CITY_TOOL_TAGS),
			)
		detail = await self.get_family(family_id)
		assert detail is not None
		return detail

	async def run_wedge_demo(
		self,
		*,
		family_id: UUID | None = None,
		goal: str | None = None,
		family_name: str = "Wedge City Family",
	) -> dict[str, Any]:
		"""
		Seed (if needed), start a build+run job, and have multiple children contribute.

		Executor writes + runs Python; analyst/creative/empath/builder write commons notes.
		"""
		if family_id is not None:
			family = await self.get_family(family_id)
			if family is None:
				raise ValueError("Family not found")
		else:
			family = await self.seed_wedge_family(name=family_name)

		fid = UUID(family["id"])
		members = family.get("members") or []
		by_role: dict[str, dict[str, Any]] = {}
		for m in members:
			label = m.get("role_label") or m.get("role_in_family")
			if label and label not in by_role:
				by_role[str(label)] = m

		job_goal = goal or "Build hello.py in the commons and run it; siblings leave notes."
		job = await self.start_job(family_id=fid, goal=job_goal, district=CityDistrict.BUILD.value)
		job_id = UUID(job["id"])

		contributions: list[dict[str, Any]] = []

		async def _as(role: str, calls: list[dict[str, Any]]) -> None:
			member = by_role.get(role)
			agent_id = UUID(member["agent_id"]) if member and member.get("agent_id") else None
			result = await self.execute_tool_calls(job_id, calls, agent_id=agent_id)
			contributions.append({"role": role, "agent_id": str(agent_id) if agent_id else None, **result})

		await _as(
			"analyst",
			[
				{
					"name": "workspace_write",
					"args": {
						"path": "notes/analysis.md",
						"content": "# Analysis\nGoal is clear: ship a runnable hello artifact.\nSuccess = stdout contains wedge marker.\n",
					},
				}
			],
		)
		await _as(
			"creative",
			[
				{
					"name": "workspace_write",
					"args": {
						"path": "notes/spark.md",
						"content": "# Spark\nMake the script greet the city by name.\n",
					},
				},
				{
					"name": "emit_viz_event",
					"args": {"event_type": "viz.pulse", "payload": {"from": "creative", "mood": "excited"}},
				},
			],
		)
		await _as(
			"empath",
			[
				{
					"name": "workspace_write",
					"args": {
						"path": "notes/users.md",
						"content": "# Users\nOperators need to see who built and who ran.\n",
					},
				}
			],
		)
		await _as(
			"builder",
			[
				{
					"name": "workspace_write",
					"args": {
						"path": "notes/build.md",
						"content": "# Build plan\n1. Write hello.py\n2. run_python\n3. Confirm stdout\n",
					},
				}
			],
		)
		await _as(
			"executor",
			[
				{
					"name": "workspace_write",
					"args": {
						"path": "hello.py",
						"content": (
							'print("persola-city-wedge")\n'
							'print("sum", 1 + 2 + 3)\n'
						),
					},
				},
				{"name": "run_python", "args": {"path": "hello.py"}},
			],
		)

		# Cohesion merge event from parent/coordinator
		parent = by_role.get("coordinator") or next(
			(m for m in members if m.get("role_in_family") == "parent"),
			None,
		)
		parent_agent = UUID(parent["agent_id"]) if parent and parent.get("agent_id") else None
		child_ids = [
			m["agent_id"]
			for m in members
			if m.get("role_in_family") == "child" and m.get("agent_id")
		]
		await self.execute_tool_calls(
			job_id,
			[
				{
					"name": "emit_viz_event",
					"args": {
						"event_type": "cohesion.merge",
						"payload": {
							"summary": "Wedge demo: siblings contributed notes; executor built and ran hello.py",
							"roles": list(by_role.keys()),
							"parent_id": parent.get("id") if parent else None,
							"parent_agent_id": str(parent_agent) if parent_agent else None,
							"child_ids": child_ids,
						},
					},
				}
			],
			agent_id=parent_agent,
		)

		runs = await self.list_runs(job_id)
		arts = await self.list_artifacts(job_id)
		succeeded = any(r.get("status") == "succeeded" and r.get("tool") == "run_python" for r in runs)
		await self.set_job_status(
			job_id,
			status=CityJobStatus.COMPLETED.value if succeeded else CityJobStatus.FAILED.value,
			result_summary="wedge demo completed" if succeeded else "wedge demo failed run_python",
			result={
				"artifact_count": len(arts),
				"run_count": len(runs),
				"contributions": len(contributions),
			},
		)

		detail = await self.get_job(job_id)
		return {
			"family": await self.get_family(fid),
			"job": detail,
			"artifacts": arts,
			"runs": runs,
			"events": await self.list_events(job_id=job_id),
			"contributions": contributions,
			"success": succeeded,
		}

	# ── Phase 5 scale ────────────────────────────────────────────────────

	async def cohesion_score(self, job_id: UUID) -> dict[str, Any]:
		"""
		Cohesion ∈ [0,1]: fraction of family members who authored an artifact
		or started a run on this job, blended with tool success rate.
		"""
		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		members = await self.members.list_for_family(job.family_id)
		member_agents = {str(m.agent_id) for m in members}
		arts = await self.artifacts.list_for_job(job_id, limit=1000)
		runs = await self.runs.list_for_job(job_id, limit=1000)
		authors = {
			str(a.created_by_agent_id)
			for a in arts
			if a.created_by_agent_id and str(a.created_by_agent_id) in member_agents
		}
		runners = {
			str(r.started_by_agent_id)
			for r in runs
			if r.started_by_agent_id and str(r.started_by_agent_id) in member_agents
		}
		participants = authors | runners
		participation = (len(participants) / len(member_agents)) if member_agents else 0.0
		succeeded = sum(1 for r in runs if r.status == WorkspaceRunStatus.SUCCEEDED.value)
		success_rate = (succeeded / len(runs)) if runs else 0.0
		score = round(0.6 * participation + 0.4 * success_rate, 4)
		return {
			"job_id": str(job_id),
			"score": score,
			"participation": round(participation, 4),
			"tool_success_rate": round(success_rate, 4),
			"participants": len(participants),
			"family_size": len(member_agents),
			"artifact_count": len(arts),
			"run_count": len(runs),
		}

	async def scale_probe(
		self,
		*,
		families: int | None = None,
		agents_per_family: int | None = None,
		name_prefix: str = "ScaleProbe",
		run_jobs: bool = True,
	) -> dict[str, Any]:
		"""
		Sustained probe: create ≥5 families × N agents (default 50 total) and
		optionally run a tiny build+run job per family.
		"""
		cfg = DEFAULT_SCALE_CONFIG
		n_families = max(1, families if families is not None else cfg.probe_families)
		per_family = max(2, agents_per_family if agents_per_family is not None else cfg.probe_agents_per_family)
		# per_family includes parent, so children = per_family - 1
		children = max(1, per_family - 1)

		created_families: list[dict[str, Any]] = []
		jobs: list[dict[str, Any]] = []
		total_agents = 0

		for i in range(n_families):
			district = ("build", "viz", "research", "ops")[i % 4]
			family = await self.create_family(
				name=f"{name_prefix}-{i + 1}",
				description=f"Phase 5 scale probe family {i + 1}",
				default_district=district,
				parent_name=f"{name_prefix} Parent {i + 1}",
				role_label="coordinator",
				policy={"scale_probe": True, "shard": f"district:{district}"},
			)
			fid = UUID(family["id"])
			for c in range(children):
				role = ("analyst", "creative", "executor", "empath", "builder")[c % 5]
				await self.spawn_child(
					fid,
					name=f"{name_prefix}-{i + 1}-C{c + 1}",
					role_label=role,
					knob_overrides={"creativity": 0.4 + (c % 5) * 0.1},
				)
			detail = await self.get_family(fid)
			assert detail is not None
			created_families.append(detail)
			total_agents += len(detail["members"])

			if run_jobs:
				job = await self.start_job(
					family_id=fid,
					goal=f"probe write+run for {detail['name']}",
					district=district,
				)
				# Prefer an executor-ish child; fall back to any child
				agent_id = None
				for m in detail["members"]:
					if m.get("role_label") == "executor":
						agent_id = UUID(m["agent_id"])
						break
				if agent_id is None:
					child = next((m for m in detail["members"] if m["role_in_family"] == "child"), None)
					agent_id = UUID(child["agent_id"]) if child else None
				await self.execute_tool_calls(
					UUID(job["id"]),
					[
						{
							"name": "workspace_write",
							"args": {
								"path": f"probe/{i}.py",
								"content": f'print("probe-{i}")\n',
							},
						},
						{"name": "run_python", "args": {"path": f"probe/{i}.py"}},
					],
					agent_id=agent_id,
				)
				await self.set_job_status(
					UUID(job["id"]),
					status=CityJobStatus.COMPLETED.value,
					result_summary="scale probe job",
				)
				jobs.append(await self.get_job(UUID(job["id"])) or job)

		try:
			from ..metrics import set_city_active_agents

			set_city_active_agents(total_agents)
		except Exception:
			pass

		return {
			"families": len(created_families),
			"agents": total_agents,
			"jobs": len(jobs),
			"family_ids": [f["id"] for f in created_families],
			"job_ids": [j["id"] for j in jobs if j],
			"meets_probe_bar": total_agents >= 50 and len(created_families) >= 5,
			"model_tiers": {
				"parent": self.model_tiers.parent,
				"child": self.model_tiers.child,
			},
			"path_to_100": {
				"current_agents": total_agents,
				"target": cfg.target_agents,
				"next": "raise workers + per-family concurrency; shard by district; keep child models cheap",
			},
		}

	async def bulk_cyrex_sync(self, family_id: UUID) -> dict[str, Any]:
		"""Push all family member personas to Cyrex when configured."""
		from ..integrations.cyrex import CyrexClient

		family = await self.get_family(family_id)
		if family is None:
			raise ValueError("Family not found")
		client = CyrexClient()
		if not client.is_configured:
			return {
				"configured": False,
				"synced": 0,
				"results": [],
				"detail": "Cyrex is not configured (set CYREX_URL and CYREX_API_KEY)",
			}

		results: list[dict[str, Any]] = []
		for m in family["members"]:
			agent = await self.agents.get(UUID(m["agent_id"]))
			if agent is None or not agent.persona_id:
				results.append({"agent_id": m["agent_id"], "ok": False, "error": "no persona"})
				continue
			persona = await self.personas.get(agent.persona_id)
			if persona is None:
				results.append({"agent_id": m["agent_id"], "ok": False, "error": "persona missing"})
				continue
			try:
				payload = await client.push_persona(persona.to_profile())
				results.append({"agent_id": m["agent_id"], "ok": True, "response": payload})
			except Exception as exc:  # noqa: BLE001
				results.append({"agent_id": m["agent_id"], "ok": False, "error": str(exc)})

		return {
			"configured": True,
			"family_id": str(family_id),
			"synced": sum(1 for r in results if r.get("ok")),
			"results": results,
		}

	async def enqueue_job_tools(
		self,
		job_id: UUID,
		calls: list[dict[str, Any]],
		*,
		agent_id: UUID | None = None,
		wait: bool = False,
	) -> dict[str, Any]:
		from ..orchestration.city_worker import enqueue_city_tools

		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		item = await enqueue_city_tools(
			job_id=job_id,
			family_id=job.family_id,
			district=job.district,
			calls=calls,
			agent_id=agent_id,
			wait=wait,
		)
		return {
			"work_id": item.id,
			"status": item.status,
			"job_id": str(job_id),
			"district": job.district,
			"queue": True,
			"error": item.error,
			"result": item.result,
		}

	async def invoke_team_on_job(
		self,
		job_id: UUID,
		task: str,
		*,
		llm_fn,
		agent_id: UUID | None = None,
		use_langgraph: bool = True,
	) -> dict[str, Any]:
		"""
		Phase 2/5 bridge: TeamOrchestrator with city commons tools bound to this job.
		Structured tool_calls in specialist output invoke workspace_*/run_python.
		"""
		from ..orchestration.city_tools import build_city_registry
		from ..orchestration.team import TeamOrchestrator
		from ..orchestration.state import TeamSessionState

		job = await self.jobs.get(job_id)
		if job is None:
			raise ValueError("Job not found")
		if job.status == CityJobStatus.PENDING.value:
			job.status = CityJobStatus.RUNNING.value
			await self.db.flush()

		registry = await build_city_registry(
			f"city-team-{job_id}",
			db=self.db,
			job_id=job_id,
			agent_id=agent_id,
		)
		orch = TeamOrchestrator(
			llm_fn=llm_fn,
			tool_registry=registry,
			use_langgraph=use_langgraph,
		)
		session = TeamSessionState(session_id=f"city-job-{job_id}")
		result = await orch.run(task, session=session)
		payload = result.to_dict()
		payload["job_id"] = str(job_id)
		payload["city_tools"] = [t["name"] for t in registry.list_tools() if "city" in (t.get("tags") or [])]
		await self.db.commit()
		return payload
