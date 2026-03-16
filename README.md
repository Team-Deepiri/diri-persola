# Deepiri Persola

Agentic Personality Framework - Create AI agents with customizable personalities.

## Features

- **40 Tunable Parameters** - Fine-tune across 4 panels: Creativity, Personality, Thinking, Reliability
- **Writing Sample Analysis** - Upload samples to extract personality traits
- **Multi-Model Support** - OpenAI, Anthropic, Ollama
- **Cyrex Integration** - Spawn agents into Cyrex
- **Persona Blending** - Combine personas
- **Real-time Playground** - Test and iterate

## Installation

```bash
pip install deepiri-persola
```

## Quick Start

### CLI

```bash
# Create a persona
persola persona create --name "Friendly Assistant" --description "A warm and helpful assistant"

# List knobs
persola tuning knobs

# Analyze writing samples
persola analyze tone "Your text here"

# Blend personas
persola blend create --knobs1 '{"humor": 0.5}' --knobs2 '{"humor": 0.8}'
```

### API Server

```bash
# Start the server
persola-server

# Or with custom settings
uvicorn persola.api.main:app --host 0.0.0.0 --port 8002
```

### Python API

```python
from persola import PersonaProfile, PersonaEngine, SamplingEngine

# Create a persona
profile = PersonaProfile(
    name="My Assistant",
    creativity=0.7,
    empathy=0.8,
    humor=0.5,
)

# Generate system prompt
engine = PersonaEngine()
prompt = engine.build_system_prompt(profile)

# Get sampling params
sampling = engine.get_sampling_params(profile)
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health check
- `POST /api/v1/personas` - Create persona
- `GET /api/v1/personas` - List personas
- `GET /api/v1/personas/{id}` - Get persona
- `PUT /api/v1/personas/{id}` - Update persona
- `DELETE /api/v1/personas/{id}` - Delete persona
- `POST /api/v1/personas/blend` - Blend personas
- `GET /api/v1/personas/{id}/system-prompt` - Get generated prompt
- `GET /api/v1/tuning/knobs` - Get knob definitions
- `POST /api/v1/tuning/validate` - Validate knobs
- `POST /api/v1/agents` - Create agent
- `GET /api/v1/agents` - List agents
- `POST /api/v1/agents/{id}/invoke` - Invoke agent
- `GET /api/v1/presets` - Get presets
- `POST /api/v1/presets/{id}/apply` - Apply preset

## Docker

```bash
docker-compose up persola
```

## Architecture

```
persola/
├── core/           # PersonaProfile, Engine, Sampling
├── personality/   # Tone analysis
├── tuning/        # Knob registry
├── pipelines/     # Generation pipelines
├── integrations/  # Model adapters, Cyrex bridge
├── api/           # FastAPI server
└── ui/            # Web UI
```

## License

MIT
