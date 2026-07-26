"""Communal city API — families, lineage, jobs, commons, events."""

from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..db.models import CityDistrict, CityJobStatus
from ..orchestration.city_tools import register_city_tools
from ..orchestration.tool_calls import parse_tool_calls
from ..orchestration.tools import ToolRegistry
from ..services.city_service import CityService

router = APIRouter(prefix="/api/v1/city", tags=["city"])


class _InMemoryTokenBucket:
	"""Process-local rate limiter so city APIs do not depend on Redis."""

	def __init__(self, capacity: float = 60.0, refill_rate: float = 1.0) -> None:
		self.capacity = capacity
		self.refill_rate = refill_rate
		self._buckets: dict[str, tuple[float, float]] = {}

	def consume(self, identifier: str) -> bool:
		now = time.monotonic()
		tokens, last = self._buckets.get(identifier, (self.capacity, now))
		tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
		if tokens < 1.0:
			self._buckets[identifier] = (tokens, now)
			return False
		self._buckets[identifier] = (tokens - 1.0, now)
		return True


_city_bucket = _InMemoryTokenBucket(capacity=60.0, refill_rate=1.0)


async def _city_rate_limit(request: Request) -> None:
	identifier = get_remote_address(request)
	if not _city_bucket.consume(identifier):
		raise HTTPException(status_code=429, detail="City API rate limit exceeded")


class CreateFamilyRequest(BaseModel):
	name: str = Field(..., min_length=1, max_length=255)
	description: Optional[str] = None
	default_district: str = Field(default=CityDistrict.BUILD.value)
	policy: dict[str, Any] = Field(default_factory=dict)
	parent_agent_id: Optional[str] = None
	parent_name: Optional[str] = None
	persona_id: Optional[str] = None
	tool_tags: Optional[list[str]] = None
	role_label: Optional[str] = "coordinator"


class SpawnChildRequest(BaseModel):
	name: str = Field(..., min_length=1, max_length=255)
	knob_overrides: dict[str, float] = Field(default_factory=dict)
	tool_tags: Optional[list[str]] = None
	role_label: Optional[str] = None
	parent_member_id: Optional[str] = None
	description: Optional[str] = None


class StartJobRequest(BaseModel):
	family_id: str
	goal: str = Field(..., min_length=1)
	district: Optional[str] = None
	team_session_id: Optional[str] = None
	status: str = Field(default=CityJobStatus.PENDING.value)


class ExecuteToolsRequest(BaseModel):
	calls: list[dict[str, Any]] = Field(default_factory=list)
	text: Optional[str] = None
	agent_id: Optional[str] = None


class InvokeJobRequest(BaseModel):
	"""Execute structured tool calls for a job (Phase 2 build+run path)."""

	calls: list[dict[str, Any]] = Field(default_factory=list)
	text: Optional[str] = None
	agent_id: Optional[str] = None
	complete: bool = True


class WedgeSeedRequest(BaseModel):
	name: str = Field(default="Wedge City Family", min_length=1, max_length=255)


class WedgeRunRequest(BaseModel):
	family_id: Optional[str] = None
	family_name: str = Field(default="Wedge City Family", min_length=1, max_length=255)
	goal: Optional[str] = None


class ScaleProbeRequest(BaseModel):
	mode: str = Field(default="fifty", pattern="^(fifty|hundred)$")
	families: Optional[int] = Field(default=None, ge=1, le=20)
	agents_per_family: Optional[int] = Field(default=None, ge=2, le=25)
	name_prefix: str = Field(default="ScaleProbe", min_length=1, max_length=64)
	run_jobs: bool = True


class EnqueueToolsRequest(BaseModel):
	calls: list[dict[str, Any]] = Field(default_factory=list)
	agent_id: Optional[str] = None
	wait: bool = False


class TeamInvokeJobRequest(BaseModel):
	task: str = Field(..., min_length=1)
	agent_id: Optional[str] = None
	use_langgraph: bool = True


@router.get("/families")
async def list_families(limit: int = 50, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	return await service.list_families(limit=min(max(limit, 1), 200))


@router.post("/families")
async def create_family(
	request: Request,
	body: CreateFamilyRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	service = CityService(db)
	try:
		return await service.create_family(
			name=body.name,
			description=body.description,
			default_district=body.default_district,
			policy=body.policy,
			parent_agent_id=UUID(body.parent_agent_id) if body.parent_agent_id else None,
			parent_name=body.parent_name,
			persona_id=UUID(body.persona_id) if body.persona_id else None,
			tool_tags=body.tool_tags,
			role_label=body.role_label,
		)
	except ValueError as exc:
		await db.rollback()
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/families/{family_id}")
async def get_family(family_id: str, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		fid = UUID(family_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail="Invalid family_id") from exc
	detail = await service.get_family(fid)
	if detail is None:
		raise HTTPException(status_code=404, detail="Family not found")
	return detail


@router.post("/families/{family_id}/spawn")
async def spawn_child(
	family_id: str,
	body: SpawnChildRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	service = CityService(db)
	try:
		fid = UUID(family_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail="Invalid family_id") from exc
	try:
		return await service.spawn_child(
			fid,
			name=body.name,
			knob_overrides=body.knob_overrides,
			tool_tags=body.tool_tags,
			role_label=body.role_label,
			parent_member_id=UUID(body.parent_member_id) if body.parent_member_id else None,
			description=body.description,
		)
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/jobs")
async def start_job(
	body: StartJobRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	service = CityService(db)
	try:
		return await service.start_job(
			family_id=UUID(body.family_id),
			goal=body.goal,
			district=body.district,
			team_session_id=UUID(body.team_session_id) if body.team_session_id else None,
			status=body.status,
		)
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc
	except Exception as exc:
		await db.rollback()
		raise HTTPException(status_code=400, detail=f"Invalid job request: {exc}") from exc


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		jid = UUID(job_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail="Invalid job_id") from exc
	detail = await service.get_job(jid)
	if detail is None:
		raise HTTPException(status_code=404, detail="Job not found")
	return detail


@router.get("/jobs/{job_id}/artifacts")
async def list_job_artifacts(job_id: str, limit: int = 200, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		return await service.list_artifacts(UUID(job_id), limit=min(max(limit, 1), 500))
	except ValueError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/runs")
async def list_job_runs(job_id: str, limit: int = 200, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		return await service.list_runs(UUID(job_id), limit=min(max(limit, 1), 500))
	except ValueError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/events")
async def list_job_events(job_id: str, limit: int = 500, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		return await service.list_events(job_id=UUID(job_id), limit=min(max(limit, 1), 1000))
	except ValueError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/families/{family_id}/events")
async def list_family_events(family_id: str, limit: int = 500, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		return await service.list_events(family_id=UUID(family_id), limit=min(max(limit, 1), 1000))
	except ValueError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tools")
async def list_city_tools(db: AsyncSession = Depends(get_db)):
	"""List city build/run tools (preview registry without a live job)."""
	from uuid import uuid4

	registry = ToolRegistry()
	register_city_tools(registry, db=db, job_id=uuid4(), agent_id=None)
	return registry.list_tools()


@router.post("/jobs/{job_id}/tools/execute")
async def execute_job_tools(
	job_id: str,
	body: ExecuteToolsRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	service = CityService(db)
	try:
		jid = UUID(job_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail="Invalid job_id") from exc

	calls = list(body.calls)
	if body.text:
		calls.extend(parse_tool_calls(body.text))
	if not calls:
		raise HTTPException(status_code=400, detail="No tool calls provided")

	try:
		return await service.execute_tool_calls(
			jid,
			calls,
			agent_id=UUID(body.agent_id) if body.agent_id else None,
		)
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/invoke")
async def invoke_job(
	job_id: str,
	body: InvokeJobRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""
	Phase 2 job invoke: run structured tool calls on the job commons.

	Pass ``calls`` and/or ``text`` containing JSON / TOOL_CALL lines.
	When ``complete`` is true and all calls succeed, marks the job completed.
	"""
	service = CityService(db)
	try:
		jid = UUID(job_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail="Invalid job_id") from exc

	calls = list(body.calls)
	if body.text:
		calls.extend(parse_tool_calls(body.text))
	if not calls:
		raise HTTPException(status_code=400, detail="No tool calls provided")

	try:
		result = await service.execute_tool_calls(
			jid,
			calls,
			agent_id=UUID(body.agent_id) if body.agent_id else None,
		)
		all_ok = all(item.get("ok", False) for item in result.get("tool_results", []))
		if body.complete:
			await service.set_job_status(
				jid,
				status=CityJobStatus.COMPLETED.value if all_ok else CityJobStatus.FAILED.value,
				result_summary="tool invoke completed" if all_ok else "tool invoke had failures",
				result={"tool_results": result.get("tool_results", [])},
			)
		job = await service.get_job(jid)
		return {"invoke": result, "job": job}
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/wedge/seed")
async def seed_wedge_family(
	body: WedgeSeedRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Phase 3: create a parent + five specialist children for the demo."""
	service = CityService(db)
	try:
		return await service.seed_wedge_family(name=body.name)
	except ValueError as exc:
		await db.rollback()
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/wedge/run")
async def run_wedge_demo(
	body: WedgeRunRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Phase 3 wedge: seed family (optional), start job, multi-agent writes + run_python."""
	service = CityService(db)
	try:
		return await service.run_wedge_demo(
			family_id=UUID(body.family_id) if body.family_id else None,
			family_name=body.family_name,
			goal=body.goal,
		)
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/events")
async def poll_city_events(
	family_id: Optional[str] = None,
	job_id: Optional[str] = None,
	after: Optional[str] = None,
	since: Optional[str] = None,
	limit: int = 100,
	db: AsyncSession = Depends(get_db),
):
	"""
	Incremental event poll for live UIs / Austin (≤2s client poll).

	Pass ``family_id`` and/or ``job_id``. Cursor via ``after`` (event id) or ``since`` (ISO datetime).
	"""
	from datetime import datetime

	service = CityService(db)
	try:
		since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")) if since else None
		rows = await service.list_events_since(
			family_id=UUID(family_id) if family_id else None,
			job_id=UUID(job_id) if job_id else None,
			after_id=UUID(after) if after else None,
			since=since_dt,
			limit=min(max(limit, 1), 500),
		)
		return {"events": rows, "count": len(rows)}
	except ValueError as exc:
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/events/stream")
async def stream_city_events(
	family_id: Optional[str] = None,
	job_id: Optional[str] = None,
	after: Optional[str] = None,
	poll_seconds: float = 1.0,
	max_cycles: int = 0,
):
	"""
	Server-Sent Events stream of city events (Austin live contract).

	Each message is ``event: city`` with JSON data matching docs/CITY_EVENTS.md.
	Set ``max_cycles`` > 0 to end the stream after N poll loops (tests / finite clients).
	"""
	import asyncio
	import json
	from datetime import datetime

	from fastapi.responses import StreamingResponse

	from ..db.database import AsyncSessionLocal

	if not family_id and not job_id:
		raise HTTPException(status_code=400, detail="family_id or job_id required")

	family_uuid = UUID(family_id) if family_id else None
	job_uuid = UUID(job_id) if job_id else None
	after_uuid = UUID(after) if after else None
	interval = min(max(poll_seconds, 0.25), 5.0)
	cycles_limit = max(0, int(max_cycles))

	async def event_generator():
		cursor = after_uuid
		hello = {
			"event_type": "stream.hello",
			"payload": {"family_id": family_id, "job_id": job_id},
			"created_at": datetime.utcnow().isoformat(),
		}
		yield f"event: city\ndata: {json.dumps(hello)}\n\n"
		cycles = 0
		while True:
			try:
				async with AsyncSessionLocal() as session:
					service = CityService(session)
					rows = await service.list_events_since(
						family_id=family_uuid,
						job_id=job_uuid,
						after_id=cursor,
						limit=50,
					)
				for row in rows:
					yield f"event: city\ndata: {json.dumps(row)}\n\n"
					cursor = UUID(row["id"])
				yield ": keepalive\n\n"
			except Exception as exc:  # noqa: BLE001
				err = {"event_type": "stream.error", "payload": {"detail": str(exc)}}
				yield f"event: city\ndata: {json.dumps(err)}\n\n"
			cycles += 1
			if cycles_limit and cycles >= cycles_limit:
				done = {"event_type": "stream.done", "payload": {"cycles": cycles}}
				yield f"event: city\ndata: {json.dumps(done)}\n\n"
				break
			await asyncio.sleep(interval)

	return StreamingResponse(
		event_generator(),
		media_type="text/event-stream",
		headers={
			"Cache-Control": "no-cache",
			"Connection": "keep-alive",
			"X-Accel-Buffering": "no",
		},
	)


@router.get("/snapshot")
async def city_snapshot(
	event_limit: int = 80,
	db: AsyncSession = Depends(get_db),
):
	"""Multi-family city snapshot for interactive visualization (Phase 6)."""
	service = CityService(db)
	return await service.city_snapshot(event_limit=min(max(event_limit, 1), 200))


@router.get("/scale/status")
async def city_scale_status():
	"""Worker pool + concurrency governor snapshot (Phase 5)."""
	from ..orchestration.city_scale import GLOBAL_GOVERNOR
	from ..orchestration.city_worker import CITY_WORKER_POOL

	return {
		"worker_pool": CITY_WORKER_POOL.snapshot(),
		"governor": GLOBAL_GOVERNOR.snapshot(),
		"docs": "/docs/CITY_SCALE.md",
	}


@router.get("/scale/path")
async def city_scale_path():
	"""Documented path to ~100 agents — bottlenecks and mitigations."""
	from ..orchestration.city_scale import DEFAULT_SCALE_CONFIG, GLOBAL_GOVERNOR

	cfg = DEFAULT_SCALE_CONFIG
	return {
		"target_agents": cfg.target_agents,
		"probe_default": {
			"families": cfg.probe_families,
			"agents_per_family": cfg.probe_agents_per_family,
			"total": cfg.probe_families * cfg.probe_agents_per_family,
		},
		"hundred_default": {
			"families": cfg.hundred_families,
			"agents_per_family": cfg.hundred_agents_per_family,
			"total": cfg.hundred_families * cfg.hundred_agents_per_family,
		},
		"bottlenecks": [
			{
				"name": "LLM cost/latency",
				"mitigation": "Child agents use PERSOLA_CITY_CHILD_MODEL; parent uses PERSOLA_CITY_PARENT_MODEL",
			},
			{
				"name": "Tool execution fan-out",
				"mitigation": "CityWorkerPool + ConcurrencyGovernor (global / family / district / job caps)",
			},
			{
				"name": "District hot spots",
				"mitigation": "Shard jobs across build/viz/research/ops queues",
			},
			{
				"name": "Process memory",
				"mitigation": "Bound queue_maxsize; avoid retaining full LLM transcripts in worker items",
			},
			{
				"name": "Runtime spawn",
				"mitigation": "Optional Cyrex bulk sync when families leave Persola",
			},
			{
				"name": "Personality uniqueness",
				"mitigation": "Phase 6 distinct fingerprints via city_personalities (archetype + index salt)",
			},
		],
		"config": GLOBAL_GOVERNOR.snapshot()["config"],
	}


@router.post("/scale/probe")
async def city_scale_probe(
	body: ScaleProbeRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Create probe families (mode=fifty ≥50 or mode=hundred ≥100) with distinct personalities."""
	service = CityService(db)
	try:
		return await service.scale_probe(
			families=body.families,
			agents_per_family=body.agents_per_family,
			name_prefix=body.name_prefix,
			run_jobs=body.run_jobs,
			mode=body.mode,
		)
	except ValueError as exc:
		await db.rollback()
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scale/awaken")
async def city_scale_awaken(
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Phase 6: awaken a 100-agent city (10 families × 10) with unique personalities."""
	service = CityService(db)
	try:
		return await service.scale_probe(
			mode="hundred",
			name_prefix="Awaken",
			run_jobs=True,
		)
	except ValueError as exc:
		await db.rollback()
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/enqueue")
async def enqueue_job_tools(
	job_id: str,
	body: EnqueueToolsRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Enqueue tool calls onto the city worker pool (Phase 5)."""
	if not body.calls:
		raise HTTPException(status_code=400, detail="No tool calls provided")
	service = CityService(db)
	try:
		return await service.enqueue_job_tools(
			UUID(job_id),
			body.calls,
			agent_id=UUID(body.agent_id) if body.agent_id else None,
			wait=body.wait,
		)
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/team-invoke")
async def team_invoke_job(
	job_id: str,
	body: TeamInvokeJobRequest,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Run TeamOrchestrator with city commons tools bound to this job."""
	from ..integrations.llm import get_llm_provider

	service = CityService(db)
	llm = get_llm_provider()
	if not llm.is_available():
		raise HTTPException(status_code=503, detail="No LLM provider available")

	async def llm_fn(system: str, user: str) -> str:
		return await llm.chat([{"role": "user", "content": user}], system_prompt=system)

	try:
		return await service.invoke_team_on_job(
			UUID(job_id),
			body.task,
			llm_fn=llm_fn,
			agent_id=UUID(body.agent_id) if body.agent_id else None,
			use_langgraph=body.use_langgraph,
		)
	except ValueError as exc:
		await db.rollback()
		status = 404 if "not found" in str(exc).lower() else 400
		raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/cohesion")
async def job_cohesion(job_id: str, db: AsyncSession = Depends(get_db)):
	service = CityService(db)
	try:
		return await service.cohesion_score(UUID(job_id))
	except ValueError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/families/{family_id}/cyrex/sync")
async def family_cyrex_sync(
	family_id: str,
	db: AsyncSession = Depends(get_db),
	_rl: None = Depends(_city_rate_limit),
):
	"""Bulk-push family personas to Cyrex when configured."""
	service = CityService(db)
	try:
		return await service.bulk_cyrex_sync(UUID(family_id))
	except ValueError as exc:
		await db.rollback()
		raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/workers/work/{work_id}")
async def get_work_item(work_id: str):
	from ..orchestration.city_worker import CITY_WORKER_POOL

	item = CITY_WORKER_POOL.get(work_id)
	if item is None:
		raise HTTPException(status_code=404, detail="Work item not found")
	return {
		"id": item.id,
		"status": item.status,
		"job_id": str(item.job_id),
		"family_id": str(item.family_id),
		"district": item.district,
		"error": item.error,
		"result": item.result,
	}
