from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
import os
import logging
from contextlib import asynccontextmanager

from ..models import (
    PersonaProfile, AgentConfig, KNOB_DEFINITIONS, 
    PresetName, DEFAULT_PRESETS
)
from ..engine import PersonaEngine
from ..integrations.llm import get_llm_provider, HAS_CYREX
from persola.db.database import get_db, init_db, close_db
from persola.db.repositories import PersonaRepository, AgentRepository, SessionRepository, MessageRepository
from persola.db.services import PersonaService, AgentService, AnalyticsService
from persola.db.schemas import PersonaCreate, PersonaUpdate, PersonaResponse, AgentCreate, AgentUpdate, AgentResponse, SessionResponse, MessageResponse
from fastapi import Depends

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("persola.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(
    title="Persola API",
    description="Personalized Agentic Framework API",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection
async def get_persona_service(db=Depends(get_db)) -> PersonaService:
    return PersonaService(db)

async def get_agent_service(db=Depends(get_db)) -> AgentService:
    return AgentService(db)

async def get_analytics_service(db=Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)

async def get_session_repo(db=Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)

async def get_message_repo(db=Depends(get_db)) -> MessageRepository:
    return MessageRepository(db)


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


@app.post("/api/v1/personas", response_model=PersonaResponse)
async def create_persona(persona: PersonaCreate, service: PersonaService = Depends(get_persona_service)):
    model = await service.create_persona(persona)
    return PersonaResponse.model_validate(model)


@app.get("/api/v1/personas", response_model=List[PersonaResponse])
async def list_personas(service: PersonaService = Depends(get_persona_service)):
    models = await service.list_personas()
    return [PersonaResponse.model_validate(model) for model in models]


@app.get("/api/v1/personas/{persona_id}", response_model=PersonaResponse)
async def get_persona(persona_id: str, service: PersonaService = Depends(get_persona_service)):
    model = await service.get_persona(persona_id)
    if not model:
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaResponse.model_validate(model)


@app.put("/api/v1/personas/{persona_id}", response_model=PersonaResponse)
async def update_persona(persona_id: str, persona: PersonaUpdate, service: PersonaService = Depends(get_persona_service)):
    model = await service.update_persona(persona_id, persona)
    if not model:
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaResponse.model_validate(model)


@app.delete("/api/v1/personas/{persona_id}")
async def delete_persona(persona_id: str, service: PersonaService = Depends(get_persona_service)):
    deleted = await service.delete_persona(persona_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"deleted": True}


@app.post("/api/v1/personas/blend", response_model=PersonaResponse)
async def blend_personas(request: BlendRequest, service: PersonaService = Depends(get_persona_service)):
    persona1 = await service.get_persona(request.persona1_id)
    if not persona1:
        raise HTTPException(status_code=404, detail="Persona 1 not found")
    persona2 = await service.get_persona(request.persona2_id)
    if not persona2:
        raise HTTPException(status_code=404, detail="Persona 2 not found")
    
    # Convert to PersonaProfile for engine
    from ..models import PersonaProfile
    p1 = PersonaProfile.model_validate(persona1.__dict__)
    p2 = PersonaProfile.model_validate(persona2.__dict__)
    
    engine = PersonaEngine()
    blended = engine.blend_personas(p1, p2, request.ratio)
    
    # Create new persona in db
    create_data = PersonaCreate(**blended.__dict__)
    model = await service.create_persona(create_data)
    return PersonaResponse.model_validate(model)


@app.get("/api/v1/personas/{persona_id}/system-prompt")
async def get_system_prompt(persona_id: str, service: PersonaService = Depends(get_persona_service)):
    model = await service.get_persona(persona_id)
    if not model:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    from ..models import PersonaProfile
    persona = PersonaProfile.model_validate(model.__dict__)
    engine = PersonaEngine()
    prompt = engine.build_system_prompt(persona)
    return {"system_prompt": prompt}


@app.get("/api/v1/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(session_id: str, repo: MessageRepository = Depends(get_message_repo)):
    models = await repo.get_messages_for_session(session_id)
    return [MessageResponse.model_validate(model) for model in models]


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


@app.post("/api/v1/presets/{preset}/apply")
async def apply_preset(preset: PresetName, request: ApplyPresetRequest, service: PersonaService = Depends(get_persona_service)):
    model = await service.get_persona(request.persona_id)
    if not model:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    from ..models import PersonaProfile
    persona = PersonaProfile.model_validate(model.__dict__)
    engine = PersonaEngine()
    preset_profile = engine.apply_preset(preset)
    
    persona.name = preset_profile.name
    persona.description = preset_profile.description
    persona.set_knobs(preset_profile.get_knobs())
    
    update_data = PersonaUpdate(**persona.__dict__)
    updated = await service.update_persona(request.persona_id, update_data)
    return PersonaResponse.model_validate(updated)


@app.post("/api/v1/agents", response_model=AgentResponse)
async def create_agent(agent: AgentCreate, service: AgentService = Depends(get_agent_service), persona_service: PersonaService = Depends(get_persona_service)):
    # If persona_id, build system_prompt
    if agent.persona_id:
        persona = await persona_service.get_persona(agent.persona_id)
        if persona:
            from ..models import PersonaProfile
            p = PersonaProfile.model_validate(persona.__dict__)
            engine = PersonaEngine()
            agent.system_prompt = engine.build_system_prompt(p)
    
    model = await service.create_agent(agent)
    return AgentResponse.model_validate(model)


@app.get("/api/v1/agents", response_model=List[AgentResponse])
async def list_agents(service: AgentService = Depends(get_agent_service)):
    models = await service.list_agents()
    return [AgentResponse.model_validate(model) for model in models]


@app.get("/api/v1/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, service: AgentService = Depends(get_agent_service)):
    model = await service.get_agent(agent_id)
    if not model:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(model)


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
async def invoke_agent(agent_id: str, request: InvokeRequest, service: AgentService = Depends(get_agent_service)):
    model = await service.get_agent(agent_id)
    if not model:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = AgentConfig.model_validate(model.__dict__)
    
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
        
        system_prompt = agent.system_prompt or ""
        
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
