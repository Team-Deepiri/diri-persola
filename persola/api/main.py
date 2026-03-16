from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("persola.api")

app = FastAPI(
    title="Persola API",
    description="Personalized Agentic Framework API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = PersonaEngine()
personas_db: Dict[str, PersonaProfile] = {}
agents_db: Dict[str, AgentConfig] = {}


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


@app.post("/api/v1/personas", response_model=PersonaProfile)
async def create_persona(persona: PersonaProfile):
    if not persona.id:
        persona.id = f"persona_{uuid.uuid4().hex[:8]}"
    personas_db[persona.id] = persona
    return persona


@app.get("/api/v1/personas", response_model=List[PersonaProfile])
async def list_personas():
    return list(personas_db.values())


@app.get("/api/v1/personas/{persona_id}", response_model=PersonaProfile)
async def get_persona(persona_id: str):
    if persona_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona not found")
    return personas_db[persona_id]


@app.put("/api/v1/personas/{persona_id}", response_model=PersonaProfile)
async def update_persona(persona_id: str, persona: PersonaProfile):
    if persona_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona not found")
    persona.id = persona_id
    personas_db[persona_id] = persona
    return persona


@app.delete("/api/v1/personas/{persona_id}")
async def delete_persona(persona_id: str):
    if persona_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona not found")
    del personas_db[persona_id]
    return {"deleted": True}


class BlendRequest(BaseModel):
    persona1_id: str
    persona2_id: str
    ratio: float = 0.5


@app.post("/api/v1/personas/blend", response_model=PersonaProfile)
async def blend_personas(request: BlendRequest):
    if request.persona1_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona 1 not found")
    if request.persona2_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona 2 not found")
    
    blended = engine.blend_personas(
        personas_db[request.persona1_id],
        personas_db[request.persona2_id],
        request.ratio
    )
    blended.id = f"persona_{uuid.uuid4().hex[:8]}"
    personas_db[blended.id] = blended
    return blended


@app.get("/api/v1/personas/{persona_id}/system-prompt")
async def get_system_prompt(persona_id: str):
    if persona_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona not found")
    persona = personas_db[persona_id]
    prompt = engine.build_system_prompt(persona)
    return {"system_prompt": prompt}


@app.get("/api/v1/personas/{persona_id}/sampling")
async def get_sampling_params(persona_id: str):
    if persona_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona not found")
    return engine.get_sampling_params(personas_db[persona_id])


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
async def apply_preset(preset: PresetName, request: ApplyPresetRequest):
    if request.persona_id not in personas_db:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    preset_profile = engine.apply_preset(preset)
    existing = personas_db[request.persona_id]
    
    existing.name = preset_profile.name
    existing.description = preset_profile.description
    existing.set_knobs(preset_profile.get_knobs())
    
    return existing


@app.post("/api/v1/agents", response_model=AgentConfig)
async def create_agent(agent: AgentConfig):
    if not agent.agent_id:
        agent.agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    
    if agent.persona_id and agent.persona_id in personas_db:
        persona = personas_db[agent.persona_id]
        agent.system_prompt = engine.build_system_prompt(persona)
    
    agents_db[agent.agent_id] = agent
    return agent


@app.get("/api/v1/agents", response_model=List[AgentConfig])
async def list_agents():
    return list(agents_db.values())


@app.get("/api/v1/agents/{agent_id}", response_model=AgentConfig)
async def get_agent(agent_id: str):
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agents_db[agent_id]


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
async def invoke_agent(agent_id: str, request: InvokeRequest):
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = agents_db[agent_id]
    
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
        
        profile = personas_db.get(agent.persona_id) if agent.persona_id else None
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
