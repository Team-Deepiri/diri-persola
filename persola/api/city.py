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
