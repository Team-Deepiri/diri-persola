"""Team orchestration API — multi-personality agents with persisted workflows."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import TokenBucketRateLimiter
from ..db.database import get_db
from ..db.repositories import PersonaRepository
from ..integrations.llm import get_llm_provider
from ..orchestration.langgraph_runtime import langgraph_available
from ..orchestration.personalities import list_archetypes
from ..orchestration.tool_loader import build_team_registry
from ..services.team_service import TeamService

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])

_team_bucket = TokenBucketRateLimiter(capacity=30, refill_rate=0.5)


async def _team_rate_limit(request: Request) -> None:
    identifier = get_remote_address(request)
    allowed, _ = await _team_bucket.consume(identifier)
    if not allowed:
        raise HTTPException(status_code=429, detail="Team invoke rate limit exceeded")


class TeamInvokeRequest(BaseModel):
    task: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    persona_id: Optional[str] = None
    agent_id: Optional[str] = None
    use_langgraph: bool = True


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


@router.get("/personalities")
async def list_team_personalities():
    return [
        {
            "role": a.role.value,
            "name": a.name,
            "tagline": a.tagline,
            "strengths": list(a.strengths),
            "collaboration_style": a.collaboration_style,
            "system_directive": a.system_directive,
        }
        for a in list_archetypes()
    ]


@router.get("/tools")
async def list_team_tools(session_id: str = "preview"):
    registry = await build_team_registry(session_id)
    return registry.list_tools()


@router.get("/runtime")
async def team_runtime_info():
    return {
        "langgraph_available": langgraph_available(),
        "parallel_tools": True,
        "redis_memory": True,
        "persistence": "postgres",
    }


@router.get("/sessions")
async def list_team_sessions(db: AsyncSession = Depends(get_db), limit: int = 25):
    service = TeamService(db)
    return await service.list_sessions(limit=limit)


@router.get("/sessions/{session_id}")
async def get_team_session(session_id: str, db: AsyncSession = Depends(get_db)):
    service = TeamService(db)
    detail = await service.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Team session not found")
    return detail


@router.post("/sessions/{session_id}/memory/search")
async def search_team_memory(
    session_id: str,
    body: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
):
    service = TeamService(db)
    return {"query": body.query, "results": await service.search_memory(session_id, body.query)}


@router.post("/invoke")
async def invoke_team(
    request: Request,
    body: TeamInvokeRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_team_rate_limit),
):
    profile = None
    persona_uuid: UUID | None = None
    if body.persona_id:
        persona_repo = PersonaRepository(db)
        row = await persona_repo.get(UUID(body.persona_id))
        if row:
            persona_uuid = row.id
            profile = row.to_profile()

    agent_uuid: UUID | None = UUID(body.agent_id) if body.agent_id else None

    llm = get_llm_provider()
    if not llm.is_available():
        raise HTTPException(status_code=503, detail="No LLM provider available")

    async def llm_fn(system: str, user: str) -> str:
        return await llm.chat(
            [{"role": "user", "content": user}],
            system_prompt=system,
        )

    service = TeamService(db)
    try:
        result = await service.invoke(
            body.task,
            llm_fn=llm_fn,
            persona_profile=profile,
            session_id=body.session_id,
            persona_id=persona_uuid,
            agent_id=agent_uuid,
            use_langgraph=body.use_langgraph,
        )
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload = result.to_dict()
    payload["runtime"] = {
        "langgraph": body.use_langgraph and langgraph_available(),
        "persisted": True,
    }
    return payload
