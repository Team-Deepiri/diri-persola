# Persola Implementation Plan

**Version:** 0.1.0 → 1.0.0
**Date:** 2026-03-19
**Status:** In Progress

---

## Executive Summary

Persola is an agentic personality framework for tuning AI agents across 40 parameters in 4 panels. The core engine and API are functional; the primary gap is production readiness: persistent storage, session management, a richer UI, and integration with the broader Deepiri platform.

This document is the canonical implementation plan. It is organized into phases that can be executed sequentially, with each phase producing a deployable, testable milestone.

---

## Current State Inventory

### What Exists and Works
- **`persola/models.py`** — `PersonaProfile` (23 knobs, 4 panels), `AgentConfig`, 8 `DEFAULT_PRESETS`, `KNOB_DEFINITIONS`
- **`persola/engine.py`** — `PersonaEngine`: system prompt generation, sampling parameter compilation, persona blending, preset application
- **`persola/integrations/llm.py`** — Unified `PersolaLLM` with adapters for OpenAI, Anthropic, Ollama
- **`persola/api/main.py`** — Full REST API (28 endpoints) backed by in-memory dicts
- **`ui/`** — React + TypeScript + Vite frontend with TuningLab, KnobPanel, Preset selector (compiled to `dist/`)
- **`docker/Dockerfile`** — Backend image
- **`ui/Dockerfile`** + **`ui/nginx.conf`** — UI image
- **`docs/DB_IMPLEMENTATION.md`** — Detailed database implementation reference

### What Is Missing
| Gap | Impact |
|-----|--------|
| No database — data lost on restart | Blocks production use |
| No Alembic migrations | Blocks schema evolution |
| No session/message persistence | Agents have no memory |
| No `docker-compose.yml` for standalone run | Blocks local dev |
| No `.env.example` | Blocks onboarding |
| Writing sample analysis engine | README feature, not implemented |
| CLI interface | README feature, not implemented |
| Cyrex integration (`HAS_CYREX = False`) | Platform integration blocked |
| Agent management UI | UI is incomplete |
| Conversation history UI | UI is incomplete |
| No auth/authz | Blocks multi-user deployment |
| No rate limiting | API unprotected |
| No test suite | Zero automated coverage |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Deepiri Platform                      │
│  docker-compose.dev.yml (includes diri-persola compose) │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │  persola-ui  │───▶│   persola    │                  │
│  │  (nginx:3000)│    │ (FastAPI:8002)│                  │
│  └──────────────┘    └──────┬───────┘                  │
│                             │                           │
│               ┌─────────────┼──────────────┐           │
│               ▼             ▼              ▼            │
│         ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│         │persola-db│  │  Redis   │  │  Ollama  │      │
│         │(pg:5433) │  │ (cache)  │  │  (LLM)   │      │
│         └──────────┘  └──────────┘  └──────────┘      │
│                                                         │
│  Also available: OpenAI, Anthropic (external)           │
└─────────────────────────────────────────────────────────┘
```

**Data flow:**
1. UI calls `persola` API on `/api/v1/*`
2. API calls service layer → repository layer → PostgreSQL
3. For agent invocations: API fetches persona → builds prompt via `PersonaEngine` → calls LLM provider → stores response in `messages`
4. Redis used for response caching and session state (later phases)

---

## Phase 1 — Foundation: Persistence Layer

**Goal:** Replace in-memory storage with PostgreSQL. All existing endpoints continue to work; data survives restarts.

**Milestone:** `docker compose up` → create a persona → restart → persona still exists.

---

### 1.1 Docker Compose & Environment

**File: `docker-compose.yml`** (new)

```yaml
services:
  persola-db:
    image: postgres:16-alpine
    container_name: persola-db
    restart: unless-stopped
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-deepiri}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-deepiripassword}
      POSTGRES_DB: ${POSTGRES_DB:-persola}
    volumes:
      - persola_db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-deepiri}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  persola:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: persola
    restart: unless-stopped
    ports:
      - "8010:8002"
    environment:
      HOST: 0.0.0.0
      PORT: 8002
      DEBUG: "true"
      CORS_ORIGIN: "*"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-deepiri}:${POSTGRES_PASSWORD:-deepiripassword}@persola-db:5432/${POSTGRES_DB:-persola}
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://ollama:11434}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    volumes:
      - ./persola:/app/persola
      - ./alembic:/app/alembic
    command: sh -c "alembic upgrade head && uvicorn persola.api.main:app --host 0.0.0.0 --port 8002 --reload"
    depends_on:
      persola-db:
        condition: service_healthy

  persola-ui:
    build:
      context: ./ui
      dockerfile: Dockerfile
    container_name: persola-ui
    restart: unless-stopped
    ports:
      - "3000:3000"
    depends_on:
      - persola

volumes:
  persola_db_data:

networks:
  default:
    name: deepiri-dev-network
    external: true
```

**File: `.env.example`** (new)

```env
# Database
POSTGRES_HOST=persola-db
POSTGRES_PORT=5432
POSTGRES_USER=deepiri
POSTGRES_PASSWORD=deepiripassword
POSTGRES_DB=persola

# Server
HOST=0.0.0.0
PORT=8002
DEBUG=true
CORS_ORIGIN=*

# LLM
OLLAMA_BASE_URL=http://ollama:11434
DEFAULT_MODEL=llama3:8b
DEFAULT_PROVIDER=ollama
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Platform
CYREX_URL=http://cyrex:8000
CYREX_API_KEY=change-me
REDIS_HOST=redis
REDIS_PORT=6379
```

---

### 1.2 Alembic Setup

**Files to create:**

```
alembic/
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    └── 001_initial_schema.py
```

**`alembic.ini`** — points `sqlalchemy.url` to `%(DATABASE_URL)s` loaded from env.

**`alembic/env.py`** — async migration runner:
- Imports `Base` from `persola.db.models`
- Loads `DATABASE_URL` from environment
- Uses `run_async_migrations()` with `AsyncEngine`

**`alembic/versions/001_initial_schema.py`** — creates 4 tables:

```
personas
  id UUID PK
  name VARCHAR(255) NOT NULL
  description TEXT
  # Panel 1: Creativity
  creativity FLOAT DEFAULT 0.5
  humor FLOAT DEFAULT 0.5
  formality FLOAT DEFAULT 0.5
  verbosity FLOAT DEFAULT 0.5
  empathy FLOAT DEFAULT 0.5
  confidence FLOAT DEFAULT 0.5
  # Panel 2: Personality
  openness FLOAT DEFAULT 0.5
  conscientiousness FLOAT DEFAULT 0.5
  extraversion FLOAT DEFAULT 0.5
  agreeableness FLOAT DEFAULT 0.5
  neuroticism FLOAT DEFAULT 0.5
  # Panel 3: Thinking
  reasoning_depth FLOAT DEFAULT 0.5
  step_by_step FLOAT DEFAULT 0.5
  creativity_in_reasoning FLOAT DEFAULT 0.5
  synthetics FLOAT DEFAULT 0.5
  abstraction FLOAT DEFAULT 0.5
  patterns FLOAT DEFAULT 0.5
  # Panel 4: Reliability
  accuracy FLOAT DEFAULT 0.8
  reliability FLOAT DEFAULT 0.8
  caution FLOAT DEFAULT 0.5
  consistency FLOAT DEFAULT 0.8
  self_correction FLOAT DEFAULT 0.5
  transparency FLOAT DEFAULT 0.5
  # Config
  model VARCHAR(100) DEFAULT 'llama3:8b'
  temperature FLOAT DEFAULT 0.7
  max_tokens INTEGER DEFAULT 2000
  is_preset BOOLEAN DEFAULT FALSE
  created_at TIMESTAMP DEFAULT NOW()
  updated_at TIMESTAMP DEFAULT NOW()

agents
  id UUID PK
  name VARCHAR(255) NOT NULL
  role VARCHAR(100) DEFAULT 'assistant'
  model VARCHAR(100)
  temperature FLOAT
  max_tokens INTEGER
  system_prompt TEXT
  persona_id UUID FK → personas(id) ON DELETE SET NULL
  tools JSONB DEFAULT '[]'
  memory_enabled BOOLEAN DEFAULT TRUE
  is_active BOOLEAN DEFAULT TRUE
  created_at TIMESTAMP DEFAULT NOW()
  updated_at TIMESTAMP DEFAULT NOW()

sessions
  id UUID PK
  agent_id UUID FK → agents(id) ON DELETE CASCADE
  session_id VARCHAR(100) UNIQUE NOT NULL
  metadata JSONB DEFAULT '{}'
  message_count INTEGER DEFAULT 0
  last_message_at TIMESTAMP
  created_at TIMESTAMP DEFAULT NOW()

messages
  id UUID PK
  session_id UUID FK → sessions(id) ON DELETE CASCADE
  role VARCHAR(20) NOT NULL   -- user | assistant | system
  content TEXT NOT NULL
  metadata JSONB DEFAULT '{}'
  tokens_used INTEGER
  model VARCHAR(100)
  created_at TIMESTAMP DEFAULT NOW()
```

Indexes:
- `idx_personas_name` on `personas(name)`
- `idx_personas_is_preset` on `personas(is_preset)`
- `idx_agents_persona_id` on `agents(persona_id)`
- `idx_sessions_agent_id` on `sessions(agent_id)`
- `idx_sessions_session_id` on `sessions(session_id)`
- `idx_messages_session_id` on `messages(session_id)`
- `idx_messages_created_at` on `messages(created_at)`

---

### 1.3 Database Layer (`persola/db/`)

```
persola/db/
├── __init__.py
├── database.py
├── models.py
├── repositories/
│   ├── __init__.py
│   ├── base.py
│   ├── persona_repository.py
│   ├── agent_repository.py
│   ├── session_repository.py
│   └── message_repository.py
└── services/
    ├── __init__.py
    ├── persona_service.py
    └── agent_service.py
```

**`database.py`**
- `async_engine` — created from `DATABASE_URL` env var using `create_async_engine`
- `AsyncSessionLocal` — `async_sessionmaker` factory
- `get_db()` — FastAPI dependency yielding `AsyncSession`
- `init_db()` / `close_db()` — lifespan hooks
- `check_db_health()` — executes `SELECT 1`, returns bool

**`models.py`** (SQLAlchemy 2.0 mapped classes)
- `PersonaModel` — mirrors `PersonaProfile`, all 23 knob columns as `Float`
- `AgentModel` — mirrors `AgentConfig`, FK to `PersonaModel`
- `SessionModel` — conversation session, FK to `AgentModel`
- `MessageModel` — individual turn, FK to `SessionModel`
- All models use `uuid4` default for PK, `datetime.utcnow` for timestamps
- Relationships: `AgentModel.persona`, `SessionModel.agent`, `MessageModel.session`

**`repositories/base.py`**
```python
class BaseRepository(Generic[T]):
    async def get(self, id: UUID) -> T | None
    async def list(self, offset=0, limit=50) -> list[T]
    async def create(self, obj: T) -> T
    async def update(self, id: UUID, data: dict) -> T | None
    async def delete(self, id: UUID) -> bool
    async def count(self) -> int
```

**`repositories/persona_repository.py`**
```python
class PersonaRepository(BaseRepository[PersonaModel]):
    async def get_by_name(self, name: str) -> PersonaModel | None
    async def list_presets(self) -> list[PersonaModel]
    async def search(self, query: str) -> list[PersonaModel]
    async def clone(self, id: UUID, new_name: str) -> PersonaModel
    async def seed_presets(self, presets: dict) -> None  # idempotent preset seeding
```

**`repositories/agent_repository.py`**
```python
class AgentRepository(BaseRepository[AgentModel]):
    async def get_with_persona(self, id: UUID) -> AgentModel | None
    async def list_by_persona(self, persona_id: UUID) -> list[AgentModel]
    async def set_active(self, id: UUID, active: bool) -> None
```

**`repositories/session_repository.py`**
```python
class SessionRepository(BaseRepository[SessionModel]):
    async def get_by_session_id(self, session_id: str) -> SessionModel | None
    async def get_or_create(self, agent_id: UUID, session_id: str) -> SessionModel
    async def increment_message_count(self, id: UUID) -> None
```

**`repositories/message_repository.py`**
```python
class MessageRepository(BaseRepository[MessageModel]):
    async def add(self, session_id: UUID, role: str, content: str, **meta) -> MessageModel
    async def get_history(self, session_id: UUID, limit=50) -> list[MessageModel]
    async def get_recent(self, session_id: UUID, n: int) -> list[MessageModel]
```

**`services/persona_service.py`**
Thin orchestration over `PersonaRepository` + `PersonaEngine`:
```python
class PersonaService:
    async def create(self, data: dict) -> PersonaModel
    async def apply_preset(self, persona_id: UUID, preset_name: str) -> PersonaModel
    async def blend(self, id_a: UUID, id_b: UUID, ratio: float) -> PersonaModel
    async def get_system_prompt(self, id: UUID) -> str
    async def get_sampling_params(self, id: UUID) -> dict
    async def export_json(self, id: UUID) -> dict
    async def import_json(self, data: dict) -> PersonaModel
```

**`services/agent_service.py`**
Orchestrates LLM invocation + session + message storage:
```python
class AgentService:
    async def create(self, data: dict) -> AgentModel
    async def invoke(self, agent_id: UUID, message: str, session_id: str) -> dict
    async def get_conversation(self, session_id: str) -> list[MessageModel]
```

---

### 1.4 API Update (`persola/api/main.py`)

**Changes:**
1. Add `lifespan` context manager calling `init_db()` / `close_db()`
2. Remove global `personas_db` and `agents_db` dicts
3. Inject `AsyncSession` via `Depends(get_db)` on all endpoints
4. Instantiate repositories per-request or per-app (stateless repos preferred)
5. Replace all dict operations with repository calls
6. Seed default presets on startup via `PersonaRepository.seed_presets(DEFAULT_PRESETS)`

**New endpoints added in this phase:**
```
GET  /api/v1/personas/{id}/export          → export persona as JSON
POST /api/v1/personas/import               → import persona from JSON
GET  /api/v1/agents/{id}/sessions          → list sessions for agent
GET  /api/v1/sessions/{session_id}/messages → get conversation history
GET  /health                               → include db health check
```

---

### 1.5 pyproject.toml Updates

Add to `[tool.poetry.dependencies]`:
```toml
alembic = "^1.13.0"
psycopg2-binary = "^2.9.9"
greenlet = "^3.0.0"
```

(`sqlalchemy`, `asyncpg` are already present.)

---

### 1.6 Validation Checklist — Phase 1

- [ ] `docker compose up` starts `persola-db`, `persola`, `persola-ui`
- [ ] Alembic migrations run on startup with no errors
- [ ] `POST /api/v1/personas` creates a row in `personas` table
- [ ] `GET /api/v1/personas` returns the created persona after restart
- [ ] `DELETE /api/v1/personas/{id}` removes the row
- [ ] `GET /health` reports `db: healthy`
- [ ] Default presets are seeded and available via `GET /api/v1/presets`
- [ ] Agent invocation stores messages in `messages` table
- [ ] `GET /api/v1/sessions/{id}/messages` returns conversation history

---

## Phase 2 — Platform Integration

**Goal:** Persola runs as a first-class service in the Deepiri platform stack alongside Cyrex, Redis, and Ollama.

**Milestone:** `docker compose -f docker-compose.dev.yml up -d` starts the full platform including Persola with shared networking.

---

### 2.1 Platform Docker Compose Update

**File: `deepiri-platform/docker-compose.dev.yml`** (modify)

Add `include` directive:
```yaml
include:
  - path: ./diri-persola/docker-compose.yml
    project: deepiri-dev
```

Update the `persola` service entry to depend on `persola-db` (provided by included file) and connect to `deepiri-dev-network`.

Remove any reference to the non-existent `postgres-cyrex` dependency.

---

### 2.2 Cyrex Integration

`HAS_CYREX = False` in `persola/api/main.py` — enable and implement:

**`persola/integrations/cyrex.py`** (new):
```python
class CyrexClient:
    """HTTP client for the Cyrex service."""
    base_url: str  # from CYREX_URL env var
    api_key: str   # from CYREX_API_KEY env var

    async def push_persona(self, persona: PersonaProfile) -> dict
    async def pull_persona(self, cyrex_id: str) -> PersonaProfile
    async def list_cyrex_agents(self) -> list[dict]
    async def is_available(self) -> bool
```

New API endpoints:
```
POST /api/v1/cyrex/sync/{persona_id}    → push persona to Cyrex
GET  /api/v1/cyrex/agents               → list Cyrex agents
POST /api/v1/cyrex/import/{cyrex_id}    → import Cyrex agent as persona
GET  /api/v1/cyrex/status               → Cyrex availability
```

---

### 2.3 Redis Caching Layer

`Redis` is installed but unused. Add caching for expensive operations:

**`persola/cache.py`** (new):
```python
class PersonaCache:
    """Redis-backed cache for system prompts and sampling params."""
    TTL = 300  # 5 minutes

    async def get_system_prompt(self, persona_id: UUID) -> str | None
    async def set_system_prompt(self, persona_id: UUID, prompt: str) -> None
    async def get_sampling(self, persona_id: UUID) -> dict | None
    async def set_sampling(self, persona_id: UUID, params: dict) -> None
    async def invalidate(self, persona_id: UUID) -> None  # called on persona update
```

Integrate into `PersonaService.get_system_prompt()` and `PersonaService.get_sampling_params()`.

---

### 2.4 Validation Checklist — Phase 2

- [ ] `docker compose -f docker-compose.dev.yml up -d` starts all services on shared network
- [ ] Persola API accessible at `http://persola:8002` from other containers
- [ ] Cyrex integration: `/api/v1/cyrex/status` returns availability
- [ ] Redis: system prompt is cached; repeated calls hit cache (verify via logs)
- [ ] No duplicate `persola-db` containers when using platform compose

---

## Phase 3 — Writing Sample Analysis

**Goal:** Implement the "tone/style extraction from writing samples" feature described in the README.

**Milestone:** Upload a writing sample → get recommended persona knob values.

---

### 3.1 Analysis Engine

**`persola/analysis/`** (new package):

```
persola/analysis/
├── __init__.py
├── extractor.py        # WritingStyleExtractor
├── mapper.py           # StyleToKnobMapper
└── prompts.py          # LLM prompts for analysis
```

**`extractor.py`**
```python
class WritingStyleExtractor:
    """
    Sends writing sample to LLM with a structured extraction prompt.
    Returns a StyleAnalysis dataclass with detected traits.
    """
    async def extract(self, text: str) -> StyleAnalysis

@dataclass
class StyleAnalysis:
    formality: float          # 0.0–1.0
    creativity: float
    humor: float
    verbosity: float
    empathy: float
    confidence: float
    reasoning_depth: float
    # ... all 23 knobs
    confidence_score: float   # how confident the analysis is (0–1)
    notes: str                # human-readable summary
```

**`mapper.py`**
```python
class StyleToKnobMapper:
    """Maps StyleAnalysis → PersonaProfile knob values."""
    def map(self, analysis: StyleAnalysis) -> dict[str, float]
```

**`prompts.py`**
Structured LLM prompt that instructs the model to return JSON with one float per knob.

---

### 3.2 API Endpoints

```
POST /api/v1/analysis/extract
  body: { "text": "...", "create_persona": false, "persona_name": "..." }
  returns: { "knobs": {...}, "confidence": 0.87, "notes": "..." }

POST /api/v1/analysis/extract-and-create
  body: { "text": "...", "name": "My Writing Style" }
  returns: PersonaProfile
```

---

### 3.3 Validation Checklist — Phase 3

- [ ] `POST /api/v1/analysis/extract` with sample text returns JSON knob values
- [ ] Extracted knobs are within valid ranges (0.0–1.0)
- [ ] `extract-and-create` creates a persona in the database
- [ ] Analysis works with Ollama (no external API key required)
- [ ] Graceful error when LLM returns malformed JSON (retry with fallback prompt)

---

## Phase 4 — CLI Interface

**Goal:** Add a `persola` CLI for local development and scripting.

**Milestone:** `persola persona list` works from the terminal.

---

### 4.1 CLI Structure

**`persola/cli/`** (new package):

```
persola/cli/
├── __init__.py
├── main.py         # Entry point, Click group
├── commands/
│   ├── persona.py  # persola persona <subcommand>
│   ├── agent.py    # persola agent <subcommand>
│   ├── preset.py   # persola preset <subcommand>
│   └── analyze.py  # persola analyze <file>
└── output.py       # Rich table/JSON formatting
```

**Commands:**

```bash
# Persona management
persola persona list [--format table|json]
persola persona get <id>
persola persona create --name "My Bot" --preset Creative
persola persona update <id> --creativity 0.8
persola persona delete <id>
persola persona export <id> [--out file.json]
persola persona import <file.json>
persola persona blend <id-a> <id-b> --ratio 0.6

# Preset management
persola preset list
persola preset apply <persona-id> <preset-name>

# Agent management
persola agent list
persola agent create --name "Support Bot" --persona <id>
persola agent invoke <id> --message "Hello" [--session my-session]

# Writing analysis
persola analyze <file.txt> [--create --name "My Style"]

# Status
persola status          # server + db + LLM health
```

**`pyproject.toml` entry point:**
```toml
[tool.poetry.scripts]
persola = "persola.cli.main:cli"
```

---

### 4.2 Validation Checklist — Phase 4

- [ ] `persola status` prints server/db/LLM status
- [ ] `persola persona list` shows table of personas
- [ ] `persola persona create --preset Creative` creates and prints new persona
- [ ] `persola analyze sample.txt --create --name "Test"` creates persona from text
- [ ] `persola agent invoke <id> --message "hi"` returns LLM response
- [ ] CLI connects to `http://localhost:8010` by default, configurable via `--url`

---

## Phase 5 — UI Completion

**Goal:** Complete the React UI so all backend capabilities are accessible without needing the CLI or raw API calls.

**Milestone:** A user can manage personas, agents, sessions, and run conversations entirely in the browser.

---

### 5.1 Missing UI Components

**Agent Management** (`ui/src/components/AgentManager/`)
- `AgentList.tsx` — table of agents with persona name, status, action buttons
- `AgentForm.tsx` — create/edit agent, persona picker dropdown, model/max-tokens fields
- `AgentCard.tsx` — compact agent view with invoke button

**Conversation UI** (`ui/src/components/Conversation/`)
- `ConversationView.tsx` — chat bubble layout, role-labeled messages
- `MessageInput.tsx` — text input + send button + session selector
- `SessionSelector.tsx` — dropdown to switch or create sessions
- `MessageList.tsx` — paginated message history

**Writing Sample Analysis** (`ui/src/components/Analysis/`)
- `SampleUpload.tsx` — textarea or file drag-and-drop
- `AnalysisResult.tsx` — knob preview of extracted style, "Create Persona" button

**Persona Export/Import** (additions to TuningLab)
- Export button → downloads `persona-{name}.json`
- Import button → file picker → loads knobs into editor

**Persona Blend UI** (`ui/src/components/BlendTool/`)
- Two persona selectors
- Ratio slider (0.0–1.0)
- Preview of resulting knob values
- "Save as New Persona" button

---

### 5.2 Navigation Updates (`App.tsx`)

Add sidebar routes:
```
/ (TuningLab)         — already exists
/agents               — AgentManager (new)
/agents/:id/chat      — Conversation (new)
/analyze              — Writing sample analysis (new)
/blend                — Persona blend tool (new)
/personas             — Persona library list view (new)
```

---

### 5.3 API Client Updates (`ui/src/api/index.ts`)

Add missing methods:
```typescript
analysisApi.extract(text: string): Promise<StyleAnalysis>
analysisApi.extractAndCreate(text: string, name: string): Promise<PersonaProfile>
personasApi.exportPersona(id: string): Promise<Blob>
personasApi.importPersona(file: File): Promise<PersonaProfile>
sessionsApi.list(agentId: string): Promise<Session[]>
sessionsApi.getMessages(sessionId: string): Promise<Message[]>
```

---

### 5.4 Validation Checklist — Phase 5

- [ ] Can create and edit agents from the UI
- [ ] Can open a chat session with an agent and send messages
- [ ] Conversation history loads on session re-open
- [ ] Writing sample text → knobs displayed → one-click persona creation
- [ ] Export persona as JSON from UI
- [ ] Import persona JSON and see knobs loaded in editor
- [ ] Persona blend: select two personas and ratio → preview → save

---

## Phase 6 — Auth, Rate Limiting & Security

**Goal:** Make Persola safe for multi-user or internet-exposed deployment.

**Note:** This phase is scoped for internal platform use. Full OAuth/SSO is out of scope for v1.

---

### 6.1 API Key Authentication

**`persola/auth.py`** (new):
```python
class APIKeyAuth:
    """
    Simple API key middleware.
    Keys stored in environment (PERSOLA_API_KEYS=key1,key2).
    Used via X-API-Key header.
    """
    async def __call__(self, request: Request, call_next): ...
```

- Header: `X-API-Key: <key>`
- Keys comma-separated in `PERSOLA_API_KEYS` env var
- `/health`, `/`, `/ui`, `/static/*` are exempt
- Returns 401 on invalid key

---

### 6.2 Rate Limiting

Use `slowapi` (built on `limits`):

```python
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/agents/{id}/invoke")
@limiter.limit("30/minute")
async def invoke_agent(...): ...

@app.post("/api/v1/analysis/extract")
@limiter.limit("10/minute")
async def extract_style(...): ...
```

---

### 6.3 Input Validation & Sanitization

- All persona text fields (name, description): max length constraints via Pydantic
- Knob values: strict `ge=0.0, le=1.0` Pydantic constraints (already in models, verify)
- Message content: max 32,768 characters
- Writing sample input: max 50,000 characters

---

### 6.4 Validation Checklist — Phase 6

- [ ] Requests without `X-API-Key` return 401 (when auth enabled)
- [ ] `/health` responds without auth header
- [ ] 31st invoke request in a minute returns 429
- [ ] Persona name >255 chars returns 422
- [ ] Knob value 1.1 returns 422

---

## Phase 7 — Observability & Testing

**Goal:** Automated test coverage and structured logging for production operation.

---

### 7.1 Test Suite

```
tests/
├── conftest.py              # pytest fixtures: test db, test client, sample data
├── unit/
│   ├── test_engine.py       # PersonaEngine: prompt generation, blending, sampling
│   ├── test_models.py       # Pydantic model validation
│   └── test_analysis.py     # Style extractor (mock LLM)
├── integration/
│   ├── test_persona_api.py  # Full CRUD via test client + real test DB
│   ├── test_agent_api.py    # Agent create/invoke (mock LLM)
│   └── test_session_api.py  # Session + message persistence
└── e2e/
    └── test_workflow.py     # Create persona → create agent → invoke → check history
```

**pytest configuration (`pyproject.toml`):**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Test database:** SQLite in-memory via `aiosqlite` for unit/integration tests; real Postgres for e2e.

**Coverage target:** 80% line coverage on `persola/` package.

---

### 7.2 Structured Logging

Replace bare `print()` calls with `structlog`:

```python
import structlog
log = structlog.get_logger()

log.info("persona.created", persona_id=str(id), name=name)
log.info("agent.invoked", agent_id=str(id), session_id=session_id, tokens=n)
log.error("llm.error", provider=provider, error=str(e))
```

JSON log output for aggregation by platform log stack.

---

### 7.3 Metrics Endpoint

```
GET /metrics   → Prometheus-format metrics
```

Tracked:
- `persola_requests_total{method, endpoint, status}` — request count
- `persola_request_duration_seconds{endpoint}` — latency histogram
- `persola_llm_tokens_total{provider, model}` — token usage
- `persola_personas_total` — gauge of persona count
- `persola_agents_total` — gauge of agent count

---

### 7.4 Validation Checklist — Phase 7

- [ ] `pytest tests/unit/` passes with no failures
- [ ] `pytest tests/integration/` passes against test DB
- [ ] Coverage report shows ≥ 80%
- [ ] `GET /metrics` returns valid Prometheus text format
- [ ] Log output is valid JSON when `LOG_FORMAT=json`

---

## Implementation Sequence

```
Phase 1: Persistence Layer          ← start here, everything else depends on this
  └─ 1.1 docker-compose.yml
  └─ 1.2 Alembic setup
  └─ 1.3 persola/db/ package
  └─ 1.4 API update
  └─ 1.5 pyproject.toml

Phase 2: Platform Integration       ← unblocks full platform dev stack
  └─ 2.1 docker-compose.dev.yml update
  └─ 2.2 Cyrex integration
  └─ 2.3 Redis caching

Phase 3: Writing Sample Analysis    ← standalone, can be done in parallel with Phase 4
Phase 4: CLI Interface              ← standalone, can be done in parallel with Phase 3

Phase 5: UI Completion              ← depends on Phase 1, 3 (for analysis UI)

Phase 6: Auth & Security            ← should happen before internet exposure
Phase 7: Observability & Testing    ← ongoing, finalize before v1.0 tag
```

---

## File Creation Checklist

### New Files

```
diri-persola/
├── docker-compose.yml                         # Phase 1.1
├── .env.example                               # Phase 1.1
├── alembic/
│   ├── alembic.ini                            # Phase 1.2
│   ├── env.py                                 # Phase 1.2
│   ├── script.py.mako                         # Phase 1.2
│   └── versions/
│       └── 001_initial_schema.py              # Phase 1.2
├── persola/
│   ├── db/
│   │   ├── __init__.py                        # Phase 1.3
│   │   ├── database.py                        # Phase 1.3
│   │   ├── models.py                          # Phase 1.3
│   │   ├── repositories/
│   │   │   ├── __init__.py                    # Phase 1.3
│   │   │   ├── base.py                        # Phase 1.3
│   │   │   ├── persona_repository.py          # Phase 1.3
│   │   │   ├── agent_repository.py            # Phase 1.3
│   │   │   ├── session_repository.py          # Phase 1.3
│   │   │   └── message_repository.py          # Phase 1.3
│   │   └── services/
│   │       ├── __init__.py                    # Phase 1.3
│   │       ├── persona_service.py             # Phase 1.3
│   │       └── agent_service.py               # Phase 1.3
│   ├── analysis/
│   │   ├── __init__.py                        # Phase 3
│   │   ├── extractor.py                       # Phase 3
│   │   ├── mapper.py                          # Phase 3
│   │   └── prompts.py                         # Phase 3
│   ├── cache.py                               # Phase 2.3
│   ├── auth.py                                # Phase 6
│   └── cli/
│       ├── __init__.py                        # Phase 4
│       ├── main.py                            # Phase 4
│       ├── output.py                          # Phase 4
│       └── commands/
│           ├── persona.py                     # Phase 4
│           ├── agent.py                       # Phase 4
│           ├── preset.py                      # Phase 4
│           └── analyze.py                     # Phase 4
├── ui/src/components/
│   ├── AgentManager/                          # Phase 5
│   ├── Conversation/                          # Phase 5
│   ├── Analysis/                              # Phase 5
│   └── BlendTool/                             # Phase 5
├── scripts/
│   ├── init-db.sh                             # Phase 1
│   └── start.sh                               # Phase 1
└── tests/
    ├── conftest.py                            # Phase 7
    ├── unit/                                  # Phase 7
    ├── integration/                           # Phase 7
    └── e2e/                                   # Phase 7
```

### Modified Files

```
persola/api/main.py          # Phase 1.4: replace in-memory with DB, add lifespan
persola/integrations/llm.py  # Phase 2.2: enable Cyrex (HAS_CYREX = True)
pyproject.toml               # Phase 1.5: add alembic, psycopg2-binary, greenlet, click, rich
ui/src/App.tsx               # Phase 5.2: add new routes
ui/src/api/index.ts          # Phase 5.3: add missing API methods
docker/Dockerfile            # Phase 1: ensure alembic in path
README.md                    # Phase 7: update setup/env docs
deepiri-platform/
  docker-compose.dev.yml     # Phase 2.1: add include directive
```

---

## Dependency Additions

```toml
# Phase 1 — Database
alembic = "^1.13.0"
psycopg2-binary = "^2.9.9"
greenlet = "^3.0.0"

# Phase 4 — CLI
click = "^8.1.0"
rich = "^13.7.0"

# Phase 6 — Security
slowapi = "^0.1.9"

# Phase 7 — Observability
structlog = "^24.1.0"
prometheus-client = "^0.20.0"
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^5.0.0"
aiosqlite = "^0.20.0"        # for test DB
httpx = "^0.26.0"            # for TestClient (already present)
```

---

## Open Questions

1. **Multi-tenancy:** Do personas and agents need to be scoped to a user/team, or is the namespace flat for now?
2. **Cyrex API contract:** What endpoints does Cyrex expose for persona push/pull? (Required to implement Phase 2.2 fully.)
3. **Preset seeding strategy:** Should default presets be re-seeded on every startup (idempotent upsert) or only on first run?
4. **LLM provider fallback:** If Ollama is down and no API keys are set, should agent invocation queue or fail fast?
5. **Message retention:** Should old messages be pruned automatically? If so, what is the retention window?
6. **UI hosting:** Will `persola-ui` be reverse-proxied behind the platform gateway, or accessed directly on port 3000?
