from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
import uuid
import os
import logging

from ..models import (
    PersonaProfile, AgentConfig, KNOB_DEFINITIONS, 
    PresetName, DEFAULT_PRESETS
)
from ..engine import PersonaEngine
from ..integrations.llm import get_llm_provider, HAS_CYREX
from ..db import get_db, init_db, close_db, PersonaRepo, AgentRepo
from ..db.config import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("persola.api")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup: create tables. Shutdown: dispose connection pool."""
    logger.info("Initialising database …")
    await init_db()
    async with async_session() as db:
        seeded = await PersonaRepo(db).seed_presets(DEFAULT_PRESETS)
        await db.commit()
        logger.info("Preset seeding complete: %s new presets inserted.", seeded)
    logger.info("Database ready.")
    yield
    logger.info("Shutting down database …")
    await close_db()


app = FastAPI(
    title="Persola API",
    description="Personalized Agentic Framework API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = PersonaEngine()


def get_repo(db: AsyncSession = Depends(get_db)) -> PersonaRepo:
    return PersonaRepo(db)


class ClonePersonaRequest(BaseModel):
    name: str


@app.get("/")
async def root():
    return {"message": "Persola API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
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
async def get_knobs():
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
async def validate_knobs(knobs: Dict[str, float]):
    return engine.validate_knobs(knobs)


@app.post("/api/v1/personas", response_model=PersonaProfile)
async def create_persona(persona: PersonaProfile, db: AsyncSession = Depends(get_db)):
    if not persona.id:
        persona.id = f"persona_{uuid.uuid4().hex[:8]}"
    repo = PersonaRepo(db)
    return await repo.create(persona)


@app.get("/api/v1/personas", response_model=List[PersonaProfile])
async def list_personas(db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    return await repo.list_all()


@app.get("/api/v1/personas/search", response_model=List[PersonaProfile])
async def search_personas(q: str, repo: PersonaRepo = Depends(get_repo)):
    return await repo.search(q)


@app.post("/api/v1/personas/import", response_model=PersonaProfile)
async def import_persona(persona: PersonaProfile, repo: PersonaRepo = Depends(get_repo)):
    imported = persona.model_copy(deep=True)
    imported.id = f"persona_{uuid.uuid4().hex[:8]}"
    return await repo.create(imported)


@app.get("/api/v1/personas/{persona_id}", response_model=PersonaProfile)
async def get_persona(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    persona = await repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@app.post("/api/v1/personas/{persona_id}/clone", response_model=PersonaProfile)
async def clone_persona(persona_id: str, request: ClonePersonaRequest, repo: PersonaRepo = Depends(get_repo)):
    cloned = await repo.clone(persona_id, request.name)
    if cloned is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return cloned


@app.get("/api/v1/personas/{persona_id}/export")
async def export_persona(persona_id: str, repo: PersonaRepo = Depends(get_repo)):
    persona = await repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")

    return JSONResponse(
        content=jsonable_encoder(persona),
        headers={"Content-Disposition": f'attachment; filename="{persona_id}.json"'},
    )


@app.put("/api/v1/personas/{persona_id}", response_model=PersonaProfile)
async def update_persona(persona_id: str, persona: PersonaProfile, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    persona.id = persona_id
    result = await repo.update(persona_id, persona)
    if result is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return result


@app.delete("/api/v1/personas/{persona_id}")
async def delete_persona(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    deleted = await repo.delete(persona_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"deleted": True}


class BlendRequest(BaseModel):
    persona1_id: str
    persona2_id: str
    ratio: float = 0.5


@app.post("/api/v1/personas/blend", response_model=PersonaProfile)
async def blend_personas(request: BlendRequest, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    p1 = await repo.get(request.persona1_id)
    if p1 is None:
        raise HTTPException(status_code=404, detail="Persona 1 not found")
    p2 = await repo.get(request.persona2_id)
    if p2 is None:
        raise HTTPException(status_code=404, detail="Persona 2 not found")
    
    blended = engine.blend_personas(p1, p2, request.ratio)
    blended.id = f"persona_{uuid.uuid4().hex[:8]}"
    return await repo.create(blended)


@app.get("/api/v1/personas/{persona_id}/system-prompt")
async def get_system_prompt(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    persona = await repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    prompt = engine.build_system_prompt(persona)
    return {"system_prompt": prompt}


@app.get("/api/v1/personas/{persona_id}/sampling")
async def get_sampling_params(persona_id: str, db: AsyncSession = Depends(get_db)):
    repo = PersonaRepo(db)
    persona = await repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return engine.get_sampling_params(persona)


@app.get("/api/v1/presets")
async def get_presets():
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
    repo = PersonaRepo(db)
    existing = await repo.get(request.persona_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    preset_profile = engine.apply_preset(preset)
    existing.name = preset_profile.name
    existing.description = preset_profile.description
    existing.set_knobs(preset_profile.get_knobs())
    
    result = await repo.update(request.persona_id, existing)
    return result


@app.post("/api/v1/agents", response_model=AgentConfig)
async def create_agent(agent: AgentConfig, db: AsyncSession = Depends(get_db)):
    if not agent.agent_id:
        agent.agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    
    if agent.persona_id:
        persona_repo = PersonaRepo(db)
        persona = await persona_repo.get(agent.persona_id)
        if persona:
            agent.system_prompt = engine.build_system_prompt(persona)
    
    repo = AgentRepo(db)
    return await repo.create(agent)


@app.get("/api/v1/agents", response_model=List[AgentConfig])
async def list_agents(db: AsyncSession = Depends(get_db)):
    repo = AgentRepo(db)
    return await repo.list_all()

@app.get("/api/v1/agents/{agent_id}", response_model=AgentConfig)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    repo = AgentRepo(db)
    agent = await repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


class InvokeRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


@app.get("/api/v1/provider/status")
async def get_provider_status():
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


@app.post("/api/v1/agents/{agent_id}/invoke")
async def invoke_agent(agent_id: str, request: InvokeRequest, db: AsyncSession = Depends(get_db)):
    agent_repo = AgentRepo(db)
    agent = await agent_repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not HAS_CYREX:
        return {
            "agent_id": agent_id,
            "response": "[Persola] Cyrex not available. Install dependencies to enable LLM inference.",
            "message": request.message,
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
            return {
                "agent_id": agent_id,
                "response": "[Persola] No LLM provider available. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or ensure Ollama is running.",
                "message": request.message,
                "provider": provider_type,
            }
        
        profile = None
        if agent.persona_id:
            persona_repo = PersonaRepo(db)
            profile = await persona_repo.get(agent.persona_id)
        system_prompt = agent.system_prompt or (engine.build_system_prompt(profile) if profile else "")
        
        full_prompt = f"{system_prompt}\n\nUser: {request.message}\n\nAssistant:" if system_prompt else request.message
        
        response = await llm.generate(full_prompt)
        
        return {
            "agent_id": agent_id,
            "response": response,
            "message": request.message,
            "provider": llm.get_provider_type(),
        }
        
    except Exception as e:
        logger.error(f"LLM invocation error: {e}")
        return {
            "agent_id": agent_id,
            "response": f"[Persola Error] {str(e)}",
            "message": request.message,
            "error": str(e),
        }


@app.get("/ui")
async def get_ui():
    ui_path = os.path.join(os.path.dirname(__file__), "..", "ui", "index.html")
    return FileResponse(ui_path)


@app.get("/static/{path:path}")
async def get_static(path: str):
    static_path = os.path.join(os.path.dirname(__file__), "..", "ui", "static", path)
    return FileResponse(static_path)


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)


if __name__ == "__main__":
    main()
