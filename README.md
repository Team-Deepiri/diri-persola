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

## Database Configuration

Persola uses PostgreSQL with SQLAlchemy for data persistence. The database stores personas, agents, sessions, and messages.

### Standalone Setup

For standalone operation, Persola includes its own PostgreSQL database:

```bash
# Start database
docker-compose up -d persola-db

# Run migrations
docker-compose run --rm persola-api alembic upgrade head
```

### Platform Integration

When running as part of the Deepiri platform, Persola uses the shared `persola-db` service.

## Running Migrations

Database migrations are handled by Alembic:

```bash
# Check current migration status
alembic current

# Generate new migration (after schema changes)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Docker Migration

```bash
# Run migrations in container
docker-compose run --rm persola-api alembic upgrade head

# Or use the migration container
docker-compose run --rm persola-migrations
```

## Starting the Application

### Standalone Mode

Run Persola independently:

```bash
# Start all services
docker-compose up -d

# Or use the startup script
./scripts/start.sh
```

This starts:
- `persola-db` (PostgreSQL on port 5433)
- `persola-redis` (Redis on port 6379)
- `persola-api` (API on port 8002)
- `persola-ui` (UI on port 3000)

### Platform Mode

When running within the Deepiri platform:

```bash
# From deepiri-platform directory
docker-compose -f docker-compose.dev.yml up -d persola-db persola persola-ui

# Or use Persola's startup script
cd diri-persola && ./scripts/start.sh
```

## Environment Variables

Configure Persola through environment variables:

### Database
- `DATABASE_URL` - PostgreSQL connection string
- `POSTGRES_HOST` - Database host (default: persola-db)
- `POSTGRES_PORT` - Database port (default: 5432)
- `POSTGRES_USER` - Database user (default: persola)
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name (default: persola)

### Server
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8002)
- `DEBUG` - Enable debug mode (default: false)

### LLM Configuration
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://ollama:11434)
- `DEFAULT_MODEL` - Default model (default: llama3:8b)
- `DEFAULT_PROVIDER` - Default provider (default: ollama)

### External APIs
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key

### Cyrex Integration
- `CYREX_URL` - Cyrex service URL (default: http://cyrex:8000)
- `CYREX_API_KEY` - Cyrex API key

### Redis (Optional)
- `REDIS_HOST` - Redis host (default: redis)
- `REDIS_PORT` - Redis port (default: 6379)
- `REDIS_PASSWORD` - Redis password

## License

MIT
