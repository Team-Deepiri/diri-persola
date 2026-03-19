# Persola PostgreSQL Database Implementation Plan

## Overview

This document outlines the step-by-step implementation of PostgreSQL database support for Persola. The `persola-db` container will be defined once and can be started either:

1. **As part of the platform** via `docker-compose.dev.yml` (using `include`)
2. **Standalone** via `diri-persola/docker-compose.yml`

Both methods start the SAME container - no duplication.

## Architecture

```
+-------------------+     +-------------------+
| Platform Dev      |     | Persola Standalone|
| (docker-compose   |     | (docker-compose  |
|  .dev.yml)        |     |  .yml in         |
|                   |     |  diri-persola)   |
| includes:         |     |                   |
| - diri-persola/   | --> | persola-db       |
|   docker-compose  |     | persola          |
|   .yml            |     | persola-ui       |
+-------------------+     +-------------------+
        |                         |
        v                         v
+-------------------+     +-------------------+
| deepiri-dev-      |     | persola-network   |
| network           |     |                   |
| (shared network)  |     | (isolated network)|
+-------------------+     +-------------------+
        |                         |
        +-----+-----+             |
              |                   |
              v                   v
        +---------------------------+
        | persola-db                |
        | Container Name: persola-db|
        | Port: 5433:5432           |
        +---------------------------+
```

## Step-by-Step Implementation

### Step 1: Create the Standalone Docker Compose File

**File:** `diri-persola/docker-compose.yml`

Create a complete docker-compose file that defines all persola services including `persola-db`. This file will be the single source of truth for the persola stack.

Key elements:
- Service name: `persola-db` (this becomes the container name when started standalone)
- Container name explicitly set to `persola-db`
- Port mapping: `5433:5432` (5433 externally to avoid conflict with main postgres on 5432)
- Uses same credentials as platform services
- Named volume for data persistence
- Healthcheck for dependency management

### Step 2: Create Alembic Migration Setup

**Directory:** `diri-persola/alembic/`

Create the following files:

1. **alembic.ini** - Alembic configuration
   - Database URL configuration pointing to environment variables
   - Migration script location
   - Version location

2. **alembic/env.py** - Migration environment
   - Async database engine setup
   - SQLAlchemy model imports
   - Configuration loading from environment

3. **alembic/script.py.mako** - Migration template
   - Standard Alembic migration template

4. **alembic/versions/001_initial_schema.py** - Initial migration
   - Creates `personas` table
   - Creates `agents` table
   - Creates `sessions` table
   - Creates `conversation_history` table
   - Indexes for performance
   - Constraints for data integrity

### Step 3: Create Database Models

**Directory:** `diri-persola/persola/db/`

Create comprehensive database models that mirror the Pydantic models:

1. **persola/db/models.py**
   - `PersonaModel` - Full persona profiles with all tuning parameters
   - `AgentModel` - Agent configurations
   - `SessionModel` - Conversation sessions
   - `MessageModel` - Individual messages with metadata
   - `PersonaPresetModel` - Preset templates (optional)
   - All models include:
     - UUID primary keys
     - Timestamps (created_at, updated_at)
     - JSON columns for flexible data
     - Indexes on frequently queried fields
     - Relationships between models

2. **persola/db/schemas.py**
   - Pydantic schemas for request/response validation
   - These mirror the SQLAlchemy models
   - Include validation for knob values

3. **persola/db/database.py**
   - Async database engine setup
   - Session factory
   - Connection pooling configuration
   - Health check function
   - Database initialization function

4. **persola/db/repositories/** (Comprehensive Data Access Layer)

   **persola/db/repositories/base.py**
   - Abstract base repository with common CRUD operations
   - Pagination support
   - Filtering capabilities
   - Bulk operations

   **persola/db/repositories/persona_repository.py**
   - `create_persona()` - Create new persona with validation
   - `get_persona()` - Retrieve by ID
   - `get_persona_by_name()` - Find by name
   - `list_personas()` - List all with pagination
   - `update_persona()` - Update with optimistic locking
   - `delete_persona()` - Soft delete or hard delete
   - `search_personas()` - Full-text search
   - `clone_persona()` - Duplicate existing persona
   - `get_persona_presets()` - Get preset personas
   - `blend_personas()` - Create blended persona from two sources

   **persola/db/repositories/agent_repository.py**
   - `create_agent()` - Create with persona link
   - `get_agent()` - Retrieve by ID
   - `list_agents()` - List all with pagination
   - `update_agent()` - Update configuration
   - `delete_agent()` - Remove agent
   - `get_agent_with_persona()` - Include persona data
   - `list_agents_by_persona()` - Agents using specific persona
   - `update_agent_status()` - Active/inactive state

   **persola/db/repositories/session_repository.py**
   - `create_session()` - New conversation session
   - `get_session()` - Retrieve session
   - `update_session()` - Update metadata
   - `list_sessions()` - By agent or date range
   - `delete_session()` - Clean up old sessions
   - `get_session_messages()` - Conversation history

   **persola/db/repositories/message_repository.py**
   - `add_message()` - Append to conversation
   - `get_messages()` - Paginated history
   - `get_recent_messages()` - Last N messages
   - `search_messages()` - Search conversation
   - `delete_messages()` - Clean up old messages
   - `count_messages()` - Statistics

5. **persola/db/services/** (Business Logic Layer)

   **persola/db/services/persona_service.py**
   - `create_persona()` - Validation and creation
   - `apply_preset()` - Apply preset values
   - `blend_personas()` - Blend with ratio calculation
   - `validate_knobs()` - Validate tuning parameters
   - `export_persona()` - Export to JSON
   - `import_persona()` - Import from JSON

   **persola/db/services/agent_service.py**
   - `create_agent()` - With persona linking
   - `invoke_agent()` - Execute agent with persona
   - `get_agent_context()` - Build context for LLM
   - `manage_session()` - Handle conversation flow
   - `get_conversation_history()` - Full history

   **persola/db/services/analytics_service.py**
   - `get_usage_stats()` - Usage statistics
   - `get_persona_usage()` - Which personas used most
   - `get_conversation_metrics()` - Message counts, lengths
   - `cleanup_old_sessions()` - Maintenance

6. **persola/db/__init__.py**
   - Export all models, schemas, repositories, services
   - Re-export from persola.models for compatibility

### Step 4: Create Database Migrations

**File:** `diri-persola/alembic/versions/001_initial_schema.py`

Create the initial migration with:

1. **personas table**
   ```sql
   - id: UUID PRIMARY KEY
   - name: VARCHAR(255) NOT NULL
   - description: TEXT
   - creativity: FLOAT DEFAULT 0.5
   - humor: FLOAT DEFAULT 0.5
   - formality: FLOAT DEFAULT 0.5
   - verbosity: FLOAT DEFAULT 0.5
   - empathy: FLOAT DEFAULT 0.5
   - confidence: FLOAT DEFAULT 0.5
   - openness: FLOAT DEFAULT 0.5
   - conscientiousness: FLOAT DEFAULT 0.5
   - extraversion: FLOAT DEFAULT 0.5
   - agreeableness: FLOAT DEFAULT 0.5
   - neuroticism: FLOAT DEFAULT 0.5
   - reasoning_depth: FLOAT DEFAULT 0.5
   - step_by_step: FLOAT DEFAULT 0.5
   - creativity_in_reasoning: FLOAT DEFAULT 0.5
   - synthetics: FLOAT DEFAULT 0.5
   - abstraction: FLOAT DEFAULT 0.5
   - patterns: FLOAT DEFAULT 0.5
   - accuracy: FLOAT DEFAULT 0.8
   - reliability: FLOAT DEFAULT 0.8
   - caution: FLOAT DEFAULT 0.5
   - consistency: FLOAT DEFAULT 0.8
   - self_correction: FLOAT DEFAULT 0.5
   - transparency: FLOAT DEFAULT 0.5
   - system_prompt: TEXT
   - model: VARCHAR(100) DEFAULT 'llama3:8b'
   - temperature: FLOAT DEFAULT 0.7
   - max_tokens: INTEGER DEFAULT 2000
   - is_preset: BOOLEAN DEFAULT FALSE
   - created_at: TIMESTAMP DEFAULT NOW()
   - updated_at: TIMESTAMP DEFAULT NOW()
   ```

2. **agents table**
   ```sql
   - id: UUID PRIMARY KEY
   - name: VARCHAR(255) NOT NULL
   - role: VARCHAR(100) DEFAULT 'assistant'
   - model: VARCHAR(100)
   - temperature: FLOAT
   - max_tokens: INTEGER
   - system_prompt: TEXT
   - persona_id: UUID REFERENCES personas(id)
   - tools: JSONB DEFAULT '[]'
   - memory_enabled: BOOLEAN DEFAULT TRUE
   - is_active: BOOLEAN DEFAULT TRUE
   - created_at: TIMESTAMP DEFAULT NOW()
   - updated_at: TIMESTAMP DEFAULT NOW()
   ```

3. **sessions table**
   ```sql
   - id: UUID PRIMARY KEY
   - agent_id: UUID REFERENCES agents(id)
   - session_id: VARCHAR(100)
   - metadata: JSONB DEFAULT '{}'
   - message_count: INTEGER DEFAULT 0
   - last_message_at: TIMESTAMP
   - created_at: TIMESTAMP DEFAULT NOW()
   ```

4. **messages table**
   ```sql
   - id: UUID PRIMARY KEY
   - session_id: UUID REFERENCES sessions(id)
   - role: VARCHAR(20) NOT NULL (user/assistant/system)
   - content: TEXT NOT NULL
   - metadata: JSONB DEFAULT '{}'
   - tokens_used: INTEGER
   - model: VARCHAR(100)
   - created_at: TIMESTAMP DEFAULT NOW()
   ```

5. **Indexes**
   - `idx_personas_name` on personas(name)
   - `idx_personas_is_preset` on personas(is_preset)
   - `idx_agents_persona_id` on agents(persona_id)
   - `idx_sessions_agent_id` on sessions(agent_id)
   - `idx_sessions_session_id` on sessions(session_id)
   - `idx_messages_session_id` on messages(session_id)
   - `idx_messages_created_at` on messages(created_at)

6. **Version metadata table** (managed by Alembic)
   - `alembic_version` table for migration tracking

### Step 5: Update pyproject.toml

**File:** `diri-persola/pyproject.toml`

Add new dependencies:

```toml
[tool.poetry.dependencies]
# Existing database dependencies
sqlalchemy = "^2.0.0"
asyncpg = "^0.29.0"

# New database dependencies
alembic = "^1.13.0"
psycopg2-binary = "^2.9.9"
greenlet = "^3.0.0"

# For async SQLAlchemy 2.0
sqlalchemy[asyncio] = "^2.0.0"
```

### Step 6: Create Dockerfile for Migrations

**File:** `diri-persola/docker/Dockerfile.db`

Optional specialized Dockerfile for running migrations separately:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --break-system-packages poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main

COPY alembic/ ./alembic/
COPY persola/ ./persola/

ENV PYTHONPATH=/app

CMD ["alembic", "upgrade", "head"]
```

### Step 7: Create Database Initialization Script

**File:** `diri-persola/scripts/init-db.sh`

Shell script for database initialization:

```bash
#!/bin/bash
set -e

echo "Waiting for database..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "Database is up - running migrations"
alembic upgrade head

echo "Database initialization complete"
```

### Step 8: Update Main API to Use Database

**File:** `diri-persola/persola/api/main.py`

Major updates required:

1. **Add imports**
   ```python
   from persola.db.database import get_db, init_db, close_db
   from persola.db.repositories import PersonaRepository, AgentRepository, SessionRepository
   from persola.db.services import PersonaService, AgentService
   ```

2. **Add lifespan events**
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       await init_db()
       yield
       await close_db()
   ```

3. **Replace in-memory storage**
   - Remove global `personas_db` and `agents_db` dicts
   - Inject repositories via dependency injection
   - All endpoints use async database operations

4. **Update all endpoints**
   - `POST /api/v1/personas` - Use PersonaRepository.create()
   - `GET /api/v1/personas` - Use PersonaRepository.list()
   - `PUT /api/v1/personas/{id}` - Use PersonaRepository.update()
   - `DELETE /api/v1/personas/{id}` - Use PersonaRepository.delete()
   - Similar for agents

5. **Add new endpoints**
   - `GET /api/v1/personas/{id}/export` - Export persona
   - `POST /api/v1/personas/import` - Import persona
   - `GET /api/v1/stats` - Usage statistics
   - `GET /api/v1/sessions` - List sessions
   - `GET /api/v1/sessions/{id}/messages` - Get conversation

### Step 9: Create Environment Configuration

**File:** `diri-persola/.env.example`

```env
# Database Configuration
POSTGRES_HOST=persola-db
POSTGRES_PORT=5432
POSTGRES_USER=deepiri
POSTGRES_PASSWORD=deepiripassword
POSTGRES_DB=persola

# Database Connection String (constructed from above)
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Server Configuration
HOST=0.0.0.0
PORT=8002
DEBUG=true
CORS_ORIGIN=*

# LLM Configuration
OLLAMA_BASE_URL=http://ollama:11434
DEFAULT_MODEL=llama3:8b
DEFAULT_PROVIDER=ollama

# External APIs
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Cyrex Integration
CYREX_URL=http://cyrex:8000
CYREX_API_KEY=change-me

# Redis (optional caching)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
```

### Step 10: Update Docker Compose for Platform Integration

**File:** `deepiri-platform/docker-compose.dev.yml`

Add to the existing file:

1. **Include persola compose**
   ```yaml
   include:
     - path: ./diri-persola/docker-compose.yml
       project: deepiri-dev
   ```

   Note: This makes Docker Compose treat both files as ONE project, ensuring `persola-db` is only started once.

2. **Update persola service** (in docker-compose.dev.yml)
   ```yaml
   persola:
     # ... existing config ...
     environment:
       # ... existing env vars ...
       # Database - updated to use persola-db
       POSTGRES_HOST: persola-db
       POSTGRES_PORT: 5432
       POSTGRES_DB: persola
       POSTGRES_USER: deepiri
       POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-deepiripassword}
       DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-deepiri}:${POSTGRES_PASSWORD:-deepiripassword}@persola-db:5432/persola
     depends_on:
       persola-db:
         condition: service_healthy
       redis:
         condition: service_started
       ollama:
         condition: service_started
       cyrex:
         condition: service_started
   ```

   Remove reference to non-existent `postgres-cyrex`.

3. **The persola-db service will be provided by the included compose file**

### Step 11: Configure Shared Network

**File:** `diri-persola/docker-compose.yml`

Add external network reference:

```yaml
networks:
  default:
    name: deepiri-dev-network
    external: true
```

This allows persola to connect to the platform's network when started standalone, OR join the platform network when included in docker-compose.dev.yml.

### Step 12: Create Startup Script

**File:** `diri-persola/scripts/start.sh`

```bash
#!/bin/bash
set -e

# Check if we're running standalone or as part of platform
if [ -f "../docker-compose.dev.yml" ]; then
    echo "Platform docker-compose found - starting via platform"
    cd .. && docker compose -f docker-compose.dev.yml up -d persola-db persola persola-ui
else
    echo "Starting persola stack standalone"
    docker compose up -d
fi
```

### Step 13: Update README

**File:** `diri-persola/README.md`

Add documentation for:
- Database configuration
- Running migrations
- Starting standalone vs platform
- Environment variables

---

## Usage Examples

### Running Standalone

```bash
cd diri-persola

# Copy environment file
cp .env.example .env

# Start all services (persola-db, persola, persola-ui)
docker compose up -d

# View logs
docker compose logs -f persola-db

# Run migrations manually
docker compose exec persola-db psql -U deepiri -d persola -c "SELECT 1"

# Stop all
docker compose down
```

### Running via Platform

```bash
cd deepiri-platform

# Start just persola services
docker compose -f docker-compose.dev.yml up -d persola-db persola

# Or start persola with persola-ui
docker compose -f docker-compose.dev.yml up -d persola-db persola persola-ui

# Full platform start
docker compose -f docker-compose.dev.yml up -d
```

### Running Migrations

```bash
# Standalone
cd diri-persola
docker compose exec persola alembic upgrade head

# Via platform
cd deepiri-platform
docker compose -f docker-compose.dev.yml exec persola alembic upgrade head
```

---

## Service Definitions

### persola-db Service

```yaml
persola-db:
  image: postgres:16-alpine
  container_name: persola-db
  restart: unless-stopped
  logging:
    driver: "local"
    options:
      max-size: "1m"
      max-file: "1"
      compress: "false"
  ports:
    - "5433:5432"
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-deepiri}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-deepiripassword}
    POSTGRES_DB: ${POSTGRES_DB:-persola}
  volumes:
    - persola_db_data:/var/lib/postgresql/data
    - ./scripts/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql:ro
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-deepiri}"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s
  networks:
    - default
```

### persola Service

```yaml
persola:
  build:
    context: .
    dockerfile: docker/Dockerfile
  image: deepiri-persola:latest
  pull_policy: never
  container_name: persola
  restart: unless-stopped
  logging:
    driver: "local"
    options:
      max-size: "1m"
      max-file: "1"
      compress: "false"
  environment:
    HOST: 0.0.0.0
    PORT: 8002
    DEBUG: "true"
    CORS_ORIGIN: "*"
    DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-deepiri}:${POSTGRES_PASSWORD:-deepiripassword}@persola-db:5432/${POSTGRES_DB:-persola}
    POSTGRES_HOST: persola-db
    POSTGRES_PORT: 5432
    POSTGRES_DB: ${POSTGRES_DB:-persola}
    POSTGRES_USER: ${POSTGRES_USER:-deepiri}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-deepiripassword}
    OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://ollama:11434}
    DEFAULT_MODEL: ${DEFAULT_MODEL:-llama3:8b}
    DEFAULT_PROVIDER: ${DEFAULT_PROVIDER:-ollama}
    OPENAI_API_KEY: ${OPENAI_API_KEY}
    ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    CYREX_URL: ${CYREX_URL:-http://cyrex:8000}
    CYREX_API_KEY: ${CYREX_API_KEY:-change-me}
  ports:
    - "8010:8002"
  volumes:
    - ./persola:/app/persola
    - ./alembic:/app/alembic
  command: >
    sh -c "
      alembic upgrade head &&
      uvicorn persola.api.main:app --host 0.0.0.0 --port 8002 --reload
    "
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
  depends_on:
    persola-db:
      condition: service_healthy
  networks:
    - default
```

### persola-ui Service

```yaml
persola-ui:
  build:
    context: ./ui
    dockerfile: Dockerfile
  image: deepiri-persola-ui:latest
  pull_policy: never
  container_name: persola-ui
  restart: unless-stopped
  logging:
    driver: "local"
    options:
      max-size: "1m"
      max-file: "1"
      compress: "false"
  ports:
    - "3000:3000"
  environment:
    VITE_API_URL: http://persola:8002
    VITE_PORT: 3000
  depends_on:
    persola:
      condition: service_healthy
  networks:
    - default
```

---

## Volume Configuration

```yaml
volumes:
  persola_db_data:
    driver: local

networks:
  default:
    name: deepiri-dev-network
    external: true
  persola-network:
    name: persola-network
    driver: bridge
```

---

## Migration Commands Reference

```bash
# Create a new migration
docker compose exec persola alembic revision --autogenerate -m "description"

# Run pending migrations
docker compose exec persola alembic upgrade head

# Rollback last migration
docker compose exec persola alembic downgrade -1

# Show current revision
docker compose exec persola alembic current

# Show migration history
docker compose exec persola alembic history

# Show pending migrations
docker compose exec persola alembic check
```

---

## Troubleshooting

### Database Connection Issues

1. Verify persola-db is running:
   ```bash
   docker compose ps persola-db
   docker compose logs persola-db
   ```

2. Check network connectivity:
   ```bash
   docker compose exec persola ping persola-db
   ```

3. Test database connection:
   ```bash
   docker compose exec persola-db psql -U deepiri -d persola -c "SELECT 1"
   ```

### Migration Issues

1. Check current migration status:
   ```bash
   docker compose exec persola alembic current
   ```

2. Verify migration files exist:
   ```bash
   docker compose exec persola ls -la alembic/versions/
   ```

3. Manually run migrations:
   ```bash
   docker compose exec persola alembic upgrade head --sql
   ```

### Data Persistence

1. Verify volume is mounted:
   ```bash
   docker inspect persola-db | grep -A 10 Mounts
   ```

2. Check volume contents:
   ```bash
   docker compose exec persola-db ls -la /var/lib/postgresql/data/
   ```

---

## File Checklist

```
diri-persola/
├── docker-compose.yml              # NEW: Standalone compose
├── pyproject.toml                  # MODIFIED: Add deps
├── .env.example                    # NEW: Env template
├── docs/
│   └── DB_IMPLEMENTATION.md        # This document
├── alembic/
│   ├── alembic.ini                 # NEW: Alembic config
│   ├── env.py                      # NEW: Migration env
│   ├── script.py.mako              # NEW: Migration template
│   └── versions/
│       └── 001_initial_schema.py  # NEW: Initial migration
├── persola/
│   └── db/
│       ├── __init__.py            # NEW: Package init
│       ├── models.py              # NEW: SQLAlchemy models
│       ├── schemas.py             # NEW: Pydantic schemas
│       ├── database.py            # NEW: DB connection
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── base.py           # NEW: Base repository
│       │   ├── persona_repository.py
│       │   ├── agent_repository.py
│       │   ├── session_repository.py
│       │   └── message_repository.py
│       └── services/
│           ├── __init__.py
│           ├── persona_service.py
│           ├── agent_service.py
│           └── analytics_service.py
├── scripts/
│   ├── init-db.sh                 # NEW: DB init script
│   └── start.sh                   # NEW: Start script
└── docker/
    └── Dockerfile                 # MODIFIED: Add migration support
```

Platform files to modify:

```
deepiri-platform/
└── docker-compose.dev.yml         # MODIFIED: Add include, update persola
```
