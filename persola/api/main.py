from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID
import re

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
import uuid
import os
from pathlib import Path
import structlog

from ..cache import TokenBucketRateLimiter

limiter = Limiter(key_func=get_remote_address)
SAFE_STATIC_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")

# Token-bucket rate limiter for the invoke endpoint (30-token burst, 0.5 t/s refill).
# Capacity matches the slowapi limit so both layers agree on the burst ceiling.
_invoke_bucket = TokenBucketRateLimiter(capacity=30, refill_rate=0.5)


async def _invoke_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces the token-bucket limit on invoke."""
    identifier = get_remote_address(request)
    allowed, remaining = await _invoke_bucket.consume(identifier)
    if not allowed:
        # Seconds until one token is available again
        retry_after = max(1, round(1.0 / _invoke_bucket.refill_rate))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after), "X-RateLimit-Remaining": "0"},
        )

from ..analysis import StyleToKnobMapper, WritingStyleExtractor
from ..models import (
    AgentConfig,
    DEFAULT_PRESETS,
    KNOB_DEFINITIONS,
    PersonaProfile,
    PresetName,
)
from ..db.database import check_db_health, close_db, get_db, init_db
from ..db.models import AgentModel, AgentRunModel, AgentToolModel, AnalysisRunModel, PersonaModel, PersonaVersionModel
from ..db.repositories import (
    AgentRepository,
    AgentRunRepository,
    AgentToolRepository,
    AnalysisRunRepository,
    MessageRepository,
    PersonaRepository,
    PersonaVersionRepository,
    SessionRepository,
)
from ..db.services import PersonaService
from ..auth import APIKeyAuth
from ..metrics import (
    MetricsMiddleware,
    metrics_endpoint,
    record_llm_tokens,
    set_agents_total,
    set_personas_total,
)
from ..engine import PersonaEngine
from ..integrations.llm import get_llm_provider, HAS_CYREX
from ..integrations.cyrex import CyrexClient
from ..logging import configure_logging

configure_logging()
log = structlog.get_logger("persola.api")

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup: init DB, seed presets. Shutdown: dispose connection pool."""
    
    log.info("db.init")
    await init_db()
    log.info("db.ready")

    # Seed presets once at startup (idempotent)
    async for db in get_db():
        repo = PersonaRepository(db)
        await repo.seed_presets(DEFAULT_PRESETS)
        await db.commit()
        break

    yield

    log.info("db.shutdown")
    await close_db()

app = FastAPI(
    title="Persola API",
    description="Personalized Agentic Framework API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(MetricsMiddleware)
app.add_middleware(APIKeyAuth)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = PersonaEngine()
cyrex_client = CyrexClient()
style_extractor = WritingStyleExtractor()
style_mapper = StyleToKnobMapper()


def _to_persona_profile(persona: PersonaModel) -> PersonaProfile:
    return persona.to_profile()


def _to_agent_config(agent: AgentModel) -> AgentConfig:
    return agent.to_config()


def _to_persona_model(persona: PersonaProfile) -> PersonaModel:
    return PersonaModel.from_profile(persona)


def _to_agent_model(agent: AgentConfig) -> AgentModel:
    return AgentModel.from_config(agent)


def _build_persona_from_knobs(name: str, knobs: dict[str, float], notes: str) -> PersonaProfile:
    return PersonaProfile(
        name=name,
        description=notes,
        **knobs,
    )


async def _record_persona_version(
    db: AsyncSession,
    persona: PersonaModel,
    *,
    source: str,
    summary: str | None = None,
) -> None:
    repo = PersonaVersionRepository(db)
    version_number = await repo.get_latest_version_number(persona.id) + 1
    profile = _to_persona_profile(persona)
    await repo.create(
        PersonaVersionModel(
            persona_id=persona.id,
            version_number=version_number,
            source=source,
            summary=summary,
            knob_snapshot=profile.get_knobs(),
            settings_snapshot=persona.settings_values(),
        )
    )


async def _record_analysis_run(
    db: AsyncSession,
    *,
    text: str,
    knobs: dict[str, float],
    confidence: float,
    notes: str,
    persona_id: UUID | None = None,
) -> None:
    repo = AnalysisRunRepository(db)
    await repo.create(
        AnalysisRunModel(
            persona_id=persona_id,
            source_text=text,
            knobs=knobs,
            confidence_score=confidence,
            notes=notes,
            provider=style_extractor.llm.get_provider_type(),
            model=style_extractor.llm.model,
        )
    )


async def _sync_agent_tools(db: AsyncSession, agent: AgentModel, tools: list[str]) -> None:
    repo = AgentToolRepository(db)
    await repo.replace_for_agent(
        agent.id,
        [AgentToolModel.from_name(agent_id=agent.id, name=tool_name) for tool_name in tools],
    )


@app.get("/")
async def root(db: AsyncSession = Depends(get_db)):
    return {"message": "Persola API", "version": "0.1.0"}


app.add_route("/metrics", metrics_endpoint, methods=["GET"])


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = await check_db_health()
    return {
        "status": db_ok and "healthy" or "degraded",
        "database": db_ok,
        "cyrex_available": HAS_CYREX,
        "llm_provider": os.getenv("OPENAI_API_KEY") and "openai" or os.getenv("ANTHROPIC_API_KEY") and "anthropic" or "ollama",
    }


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    """Check database connectivity."""
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unreachable: {e}")


@app.get("/api/v1/tuning/knobs")
async def get_knobs(db: AsyncSession = Depends(get_db)):
    return {
        "knobs": [
            {
                "key": knob.key,
                "name": knob.name,
                "description": knob.description,
                "min_value": knob.min_value,
                "max_value": knob.max_value,
                "default": knob.default,
                "panel": knob.panel,
                "step": knob.step,
            }
            for knob in KNOB_DEFINITIONS
        ],
        "panels": ["Creativity", "Personality", "Thinking", "Reliability"]
    }


@app.post("/api/v1/tuning/validate")
async def validate_knobs(knobs: Dict[str, float], db: AsyncSession = Depends(get_db)):
    return engine.validate_knobs(knobs)


class AnalysisExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    create_persona: bool = False
    persona_name: str | None = Field(default=None, max_length=200)


class AnalysisCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    name: str = Field(min_length=1, max_length=200)


class AnalysisExtractResponse(BaseModel):
    knobs: Dict[str, float]
    confidence: float
    notes: str
    persona_id: str | None = None


async def _run_style_analysis(text: str) -> tuple[dict[str, float], float, str]:
    analysis = await style_extractor.extract(text)
    knobs = style_mapper.map(analysis)
    validation = engine.validate_knobs(knobs)
    if not validation["valid"]:
        raise HTTPException(status_code=502, detail="Analysis produced invalid knob values")
    return knobs, analysis.confidence_score, analysis.notes


@app.post("/api/v1/analysis/extract", response_model=AnalysisExtractResponse)
@limiter.limit("10/minute")
async def extract_analysis(request: Request, body: AnalysisExtractRequest, db: AsyncSession = Depends(get_db)):
    knobs, confidence, notes = await _run_style_analysis(body.text)
    persona_id: str | None = None
    persona_uuid: UUID | None = None

    if body.create_persona:
        persona_name = body.persona_name or "Writing Style Persona"
        repo = PersonaRepository(db)
        persona = _build_persona_from_knobs(persona_name, knobs, notes)
        created = await repo.create(_to_persona_model(persona))
        await _record_persona_version(db, created, source="analysis", summary="Persona created from writing analysis")
        persona_uuid = created.id
        persona_id = str(created.id)

    await _record_analysis_run(
        db,
        text=body.text,
        knobs=knobs,
        confidence=confidence,
        notes=notes,
        persona_id=persona_uuid,
    )
    await db.commit()

    return AnalysisExtractResponse(
        knobs=knobs,
        confidence=confidence,
        notes=notes,
        persona_id=persona_id,
    )


@app.post("/api/v1/analysis/extract-and-create", response_model=PersonaProfile)
async def extract_and_create_persona(request: AnalysisCreateRequest, db: AsyncSession = Depends(get_db)):
    knobs, confidence, notes = await _run_style_analysis(request.text)
    repo = PersonaRepository(db)
    persona = _build_persona_from_knobs(request.name, knobs, notes)
    created = await repo.create(_to_persona_model(persona))
    await _record_persona_version(db, created, source="analysis", summary="Persona created from writing analysis")
    await _record_analysis_run(
        db,
        text=request.text,
        knobs=knobs,
        confidence=confidence,
        notes=notes,
        persona_id=created.id,
    )
    await db.commit()
    return _to_persona_profile(created)


class ClonePersonaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@app.post("/api/v1/personas", response_model=PersonaProfile)
async def create_persona(persona: PersonaProfile, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    # Ensure ID exists if upstream doesn't provide one
    if not getattr(persona, "id", None):
        persona.id = f"persona_{uuid.uuid4().hex[:8]}"

    created = await repo.create(_to_persona_model(persona))
    await _record_persona_version(
        db,
        created,
        source="manual",
        summary="Persona created"
    )

    await db.commit()
    log.info("persona.created", persona_id=str(created.id), name=created.name)
    personas = await PersonaRepository(db).count()
    set_personas_total(personas)
    return _to_persona_profile(created)


@app.get("/api/v1/personas", response_model=List[PersonaProfile])
async def list_personas(db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    personas = await repo.list(limit=1000)
    return [_to_persona_profile(item) for item in personas]


@app.get("/api/v1/personas/search", response_model=List[PersonaProfile])
async def search_personas(q: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    personas = await repo.search(q)
    return [_to_persona_profile(item) for item in personas]


@app.post("/api/v1/personas/import", response_model=PersonaProfile)
async def import_persona(persona: PersonaProfile, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    imported = persona.model_copy(deep=True)
    imported.id = str(uuid.uuid4())
    created = await repo.create(_to_persona_model(imported))
    await _record_persona_version(db, created, source="import", summary="Persona imported")
    await db.commit()
    return _to_persona_profile(created)


@app.get("/api/v1/personas/{persona_id}", response_model=PersonaProfile)
async def get_persona(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    persona = await repo.get(UUID(persona_id))
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return _to_persona_profile(persona)


@app.post("/api/v1/personas/{persona_id}/clone", response_model=PersonaProfile)
async def clone_persona(persona_id: str, request: ClonePersonaRequest, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    try:
        cloned = await repo.clone(UUID(persona_id), request.name)
    except ValueError:
        raise HTTPException(status_code=404, detail="Persona not found")

    await _record_persona_version(db, cloned, source="manual", summary=f"Cloned from {persona_id}")
    await db.commit()
    return _to_persona_profile(cloned)


@app.put("/api/v1/personas/{persona_id}", response_model=PersonaProfile)
async def update_persona(persona_id: str, persona: PersonaProfile, db: AsyncSession = Depends(get_db)):
    service = PersonaService(db)
    updates = {
        "name": persona.name,
        "description": persona.description,
        "creativity": persona.creativity,
        "humor": persona.humor,
        "formality": persona.formality,
        "verbosity": persona.verbosity,
        "empathy": persona.empathy,
        "confidence": persona.confidence,
        "openness": persona.openness,
        "conscientiousness": persona.conscientiousness,
        "extraversion": persona.extraversion,
        "agreeableness": persona.agreeableness,
        "neuroticism": persona.neuroticism,
        "reasoning_depth": persona.reasoning_depth,
        "step_by_step": persona.step_by_step,
        "creativity_in_reasoning": persona.creativity_in_reasoning,
        "synthetics": persona.synthetics,
        "abstraction": persona.abstraction,
        "patterns": persona.patterns,
        "accuracy": persona.accuracy,
        "reliability": persona.reliability,
        "caution": persona.caution,
        "consistency": persona.consistency,
        "self_correction": persona.self_correction,
        "transparency": persona.transparency,
        "model": persona.model,
        "temperature": persona.temperature,
        "max_tokens": persona.max_tokens,
        "updated_at": persona.updated_at,
    }
    updated = await service.update(
        UUID(persona_id),
        updates,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    await _record_persona_version(db, updated, source="manual", summary="Persona updated")
    await db.commit()
    return _to_persona_profile(updated)


@app.delete("/api/v1/personas/{persona_id}")
async def delete_persona(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    deleted = await repo.delete(UUID(persona_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found")
    await db.commit()
    count = await repo.count()
    set_personas_total(count)
    return {"deleted": True}


class BlendRequest(BaseModel):
    persona1_id: str
    persona2_id: str
    ratio: float = 0.5


@app.post("/api/v1/personas/blend", response_model=PersonaProfile)
async def blend_personas(request: BlendRequest, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    persona1 = await repo.get(UUID(request.persona1_id))
    persona2 = await repo.get(UUID(request.persona2_id))

    if persona1 is None:
        raise HTTPException(status_code=404, detail="Persona 1 not found")
    if persona2 is None:
        raise HTTPException(status_code=404, detail="Persona 2 not found")

    blended = engine.blend_personas(
        _to_persona_profile(persona1),
        _to_persona_profile(persona2),
        request.ratio
    )
    created = await repo.create(_to_persona_model(blended))
    await _record_persona_version(db, created, source="blend", summary=f"Blend ratio {request.ratio:.2f}")
    await db.commit()
    return _to_persona_profile(created)


@app.get("/api/v1/personas/{persona_id}/system-prompt")
async def get_system_prompt(persona_id: str, db: AsyncSession = Depends(get_db)):
    service = PersonaService(db)
    prompt = await service.get_system_prompt(UUID(persona_id))
    if prompt is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"system_prompt": prompt}


@app.get("/api/v1/personas/{persona_id}/sampling")
async def get_sampling_params(persona_id: str, db: AsyncSession = Depends(get_db)):
    service = PersonaService(db)
    params = await service.get_sampling_params(UUID(persona_id))
    if params is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return params


@app.get("/api/v1/personas/{persona_id}/export")
async def export_persona(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepository(db)
    persona = await repo.get(UUID(persona_id))
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return JSONResponse(
        content=jsonable_encoder(_to_persona_profile(persona)),
        headers={"Content-Disposition": f'attachment; filename="persona_{persona_id}.json"'},
    )


@app.get("/api/v1/presets")
async def get_presets(db: AsyncSession = Depends(get_db)):
    return {
        "presets": {
            k.value: {
                "name": v.name,
                "description": v.description,
                "knobs": v.get_knobs(),
            }
            for k, v in DEFAULT_PRESETS.items()
        }
    }


class ApplyPresetRequest(BaseModel):
    persona_id: str
    preset: PresetName


@app.post("/api/v1/presets/{preset}/apply")
async def apply_preset(preset: PresetName, request: ApplyPresetRequest, db: AsyncSession = Depends(get_db)):
    service = PersonaService(db)
    existing = await service.get(UUID(request.persona_id))
    if existing is None:
        raise HTTPException(status_code=404, detail="Persona not found")

    preset_profile = engine.apply_preset(preset)

    updates = {
        "name": preset_profile.name,
        "description": preset_profile.description,
        **preset_profile.get_knobs(),
    }
    updated = await service.update(existing.id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    await _record_persona_version(db, updated, source="preset", summary=f"Applied preset {preset.value}")
    await db.commit()
    return _to_persona_profile(updated)


@app.post("/api/v1/agents", response_model=AgentConfig)
async def create_agent(agent: AgentConfig, db: AsyncSession = Depends(get_db)):
    agent_repo = AgentRepository(db)
    persona_repo = PersonaRepository(db)

    model = _to_agent_model(agent)

    # Build system prompt if persona exists
    if model.persona_id:
        persona = await persona_repo.get(model.persona_id)
        if persona is not None:
            model.system_prompt = engine.build_system_prompt(_to_persona_profile(persona))

    created = await agent_repo.create(model)

    # Sync tools after creation
    await _sync_agent_tools(db, created, agent.tools)

    # Commit transaction
    await db.commit()

    # Return API-friendly config
    agents = await agent_repo.count()
    set_agents_total(agents)
    return _to_agent_config(created)  


@app.get("/api/v1/agents", response_model=List[AgentConfig])
async def list_agents(db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    agents = await repo.list(limit=1000)
    return [_to_agent_config(item) for item in agents]


@app.get("/api/v1/agents/{agent_id}", response_model=AgentConfig)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    agent = await repo.get(UUID(agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_agent_config(agent)


@app.put("/api/v1/agents/{agent_id}", response_model=AgentConfig)
async def update_agent(agent_id: str, agent: AgentConfig, db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    existing = await repo.get(UUID(agent_id))
    if existing is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = {
        "name": agent.name,
        "role": agent.role,
        "model": agent.model,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "system_prompt": agent.system_prompt,
        "persona_id": UUID(agent.persona_id) if agent.persona_id else None,
        "tools": list(agent.tools),
        "memory_enabled": agent.memory_enabled,
    }

    if agent.persona_id:
        persona_repo = PersonaRepository(db)
        persona = await persona_repo.get(UUID(agent.persona_id))
        if persona is not None:
            update_data["system_prompt"] = engine.build_system_prompt(_to_persona_profile(persona))

    updated = await repo.update(UUID(agent_id), update_data)
    await _sync_agent_tools(db, updated, agent.tools)
    await db.commit()
    return _to_agent_config(updated)


@app.delete("/api/v1/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    deleted = await repo.delete(UUID(agent_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.commit()
    count = await repo.count()
    set_agents_total(count)


@app.get("/api/v1/agents/{agent_id}/sessions")
async def list_agent_sessions(agent_id: str, db: AsyncSession = Depends(get_db)):
    session_repo = SessionRepository(db)
    sessions = await session_repo.list_by_agent(UUID(agent_id))
    return [
        {
            "id": str(item.id),
            "agent_id": str(item.agent_id),
            "session_id": item.session_id,
            "metadata": item.session_metadata,
            "message_count": item.message_count,
            "last_message_at": item.last_message_at,
            "created_at": item.created_at,
        }
        for item in sessions
    ]


@app.get("/api/v1/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    session_repo = SessionRepository(db)
    message_repo = MessageRepository(db)

    session = await session_repo.get_by_session_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    history = await message_repo.get_history(session.id, limit=1000)
    return [
        {
            "id": str(item.id),
            "session_id": str(item.session_id),
            "role": item.role,
            "content": item.content,
            "metadata": item.message_metadata,
            "tokens_used": item.tokens_used,
            "model": item.model,
            "created_at": item.created_at,
        }
        for item in history
    ]


class InvokeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_768)
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None


@app.get("/api/v1/provider/status")
async def get_provider_status(db: AsyncSession = Depends(get_db)):
    """Get LLM provider status"""
    providers = []
    
    if os.getenv("OPENAI_API_KEY"):
        providers.append({
            "type": "openai",
            "available": True,
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        })
    
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append({
            "type": "anthropic",
            "available": True,
            "model": "claude-3-sonnet-20240229",
        })
    
    providers.append({
        "type": "ollama",
        "available": True,
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        "model": os.getenv("LOCAL_LLM_MODEL", "llama3:8b"),
    })
    
    return {
        "available": True,
        "has_cyrex": HAS_CYREX,
        "providers": providers,
    }


def _require_cyrex_configured() -> None:
    if cyrex_client.is_configured:
        return
    raise HTTPException(
        status_code=503,
        detail="Cyrex is not configured. Set CYREX_URL and CYREX_API_KEY.",
    )


@app.get("/api/v1/cyrex/status")
async def get_cyrex_status(db: AsyncSession = Depends(get_db)):
    if not cyrex_client.is_configured:
        return {
            "available": False,
            "configured": False,
            "base_url": None,
        }

    return {
        "available": await cyrex_client.is_available(),
        "configured": True,
        "base_url": cyrex_client.base_url,
    }


@app.get("/api/v1/cyrex/agents")
async def list_cyrex_agents(db: AsyncSession = Depends(get_db)):
    _require_cyrex_configured()
    try:
        return {"agents": await cyrex_client.list_cyrex_agents()}
    except Exception as e:
        log.error("cyrex.list_agents.error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Cyrex request failed: {str(e)}") from e


@app.post("/api/v1/cyrex/sync/{persona_id}")
async def sync_persona_to_cyrex(persona_id: str, db: AsyncSession = Depends(get_db)):
    _require_cyrex_configured()

    persona_repo = PersonaRepository(db)
    persona = await persona_repo.get(UUID(persona_id))
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")

    try:
        payload = await cyrex_client.push_persona(_to_persona_profile(persona))
        return {
            "persona_id": persona_id,
            "synced": True,
            "cyrex_response": payload,
        }
    except Exception as e:
        log.error("cyrex.sync.error", persona_id=persona_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Cyrex sync failed: {str(e)}") from e


@app.post("/api/v1/cyrex/import/{cyrex_id}", response_model=PersonaProfile)
async def import_persona_from_cyrex(cyrex_id: str, db: AsyncSession = Depends(get_db)):
    _require_cyrex_configured()

    persona_repo = PersonaRepository(db)
    try:
        profile = await cyrex_client.pull_persona(cyrex_id)
        created = await persona_repo.create(_to_persona_model(profile))
        await _record_persona_version(db, created, source="cyrex", summary=f"Imported from Cyrex {cyrex_id}")
        await db.commit()
        return _to_persona_profile(created)
    except Exception as e:
        log.error("cyrex.import.error", cyrex_id=cyrex_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Cyrex import failed: {str(e)}") from e


@app.post("/api/v1/agents/{agent_id}/invoke")
@limiter.limit("30/minute")
async def invoke_agent(
    request: Request,
    agent_id: str,
    body: InvokeRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_invoke_rate_limit),
):
    agent_repo = AgentRepository(db)
    agent_run_repo = AgentRunRepository(db)
    persona_repo = PersonaRepository(db)
    session_repo = SessionRepository(db)
    message_repo = MessageRepository(db)

    agent = await agent_repo.get(UUID(agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    runtime_session_id = body.session_id or f"{agent_id}-default"
    session = await session_repo.get_or_create(agent.id, runtime_session_id)
    await message_repo.add(session.id, "user", body.message)
    run = await agent_run_repo.create(
        AgentRunModel(
            agent_id=agent.id,
            session_id=session.id,
            status="running",
            request_message=body.message,
            model=agent.model,
            run_metadata={"requested_at": datetime.utcnow().isoformat()},
        )
    )

    if not HAS_CYREX:
        await agent_run_repo.mark_completed(
            run.id,
            status="unavailable",
            response_message="[Persola] Cyrex not available. Install dependencies to enable LLM inference.",
            provider="none",
            model=agent.model,
        )
        await db.commit()
        return {
            "agent_id": agent_id,
            "response": "[Persola] Cyrex not available. Install dependencies to enable LLM inference.",
            "message": body.message,
            "provider": "none",
        }
    
    try:
        provider_type = "auto"
        if os.getenv("OPENAI_API_KEY"):
            provider_type = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider_type = "anthropic"
        
        llm = get_llm_provider(
            provider=provider_type,
            model=agent.model or "llama3:8b",
            temperature=agent.temperature or 0.7,
            max_tokens=agent.max_tokens or 2000,
        )
        
        if not llm.is_available():
            await agent_run_repo.mark_completed(
                run.id,
                status="unavailable",
                response_message="[Persola] No LLM provider available. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or ensure Ollama is running.",
                provider=provider_type,
                model=agent.model,
            )
            await db.commit()
            return {
                "agent_id": agent_id,
                "response": "[Persola] No LLM provider available. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or ensure Ollama is running.",
                "message": body.message,
                "provider": provider_type,
            }

        profile = await persona_repo.get(agent.persona_id) if agent.persona_id else None
        system_prompt = agent.system_prompt or (
            engine.build_system_prompt(_to_persona_profile(profile)) if profile else ""
        )
        
        full_prompt = f"{system_prompt}\n\nUser: {body.message}\n\nAssistant:" if system_prompt else body.message
        
        response = await llm.generate(full_prompt)

        await message_repo.add(
            session.id,
            "assistant",
            response,
            provider=llm.get_provider_type(),
        )
        await session_repo.increment_message_count(session.id)
        await agent_run_repo.mark_completed(
            run.id,
            status="completed",
            response_message=response,
            provider=llm.get_provider_type(),
            model=agent.model,
        )
        await db.commit()
        log.info(
            "agent.invoked",
            agent_id=agent_id,
            session_id=runtime_session_id,
            provider=llm.get_provider_type(),
            tokens=run.tokens_used,
        )
        record_llm_tokens(
            provider=llm.get_provider_type(),
            model=agent.model or "unknown",
            tokens=run.tokens_used or 0,
        )
        return {
            "agent_id": agent_id,
            "response": response,
            "message": body.message,
            "provider": llm.get_provider_type(),
        }
        
    except Exception as e:
        generic_error_message = "[Persola Error] An internal error has occurred."
        await agent_run_repo.mark_completed(
            run.id,
            status="failed",
            response_message=generic_error_message,
            provider=None,
            model=agent.model,
        )
        await db.commit()
        log.error("llm.error", provider=provider_type, agent_id=agent_id, error=str(e), exc_info=True)
        return {
            "agent_id": agent_id,
            "response": generic_error_message,
            "message": body.message,
            "error": "internal_error",
        }


@app.get("/ui")
async def get_ui(db: AsyncSession = Depends(get_db)):
    ui_path = os.path.join(os.path.dirname(__file__), "..", "ui", "index.html")
    return FileResponse(ui_path)


@app.get("/static/{path:path}")
async def get_static(path: str, db: AsyncSession = Depends(get_db)):
    static_root = Path(os.path.dirname(__file__), "..", "ui", "static").resolve()
    requested_path = Path(path)

    if requested_path.is_absolute() or "\x00" in path:
        raise HTTPException(status_code=403, detail="Forbidden")

    parts = requested_path.parts
    if (
        not parts
        or any(part in ("", ".", "..") for part in parts)
        or any(not SAFE_STATIC_SEGMENT.fullmatch(part) for part in parts)
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    static_path = (static_root / requested_path).resolve()

    try:
        static_path.relative_to(static_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not static_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(static_path))


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)


if __name__ == "__main__":
    main()
