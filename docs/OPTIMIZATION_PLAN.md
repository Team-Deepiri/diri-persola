# Persola Architecture Optimization Plan

**Status:** Draft
**Audience:** Persola builders
**Related:** [COMMUNAL_CITY_ROADMAP.md](./COMMUNAL_CITY_ROADMAP.md), [SCHEMA_INTEGRATION_REBRAND_MAP.md](./SCHEMA_INTEGRATION_REBRAND_MAP.md)
**Baseline:** Functionality phase complete (PR #60 merged); Phases 0–13 of communal city roadmap marked done.

---

## 1. Purpose

This plan captures every architectural improvement identified during the optimization-layer audit of the existing codebase. It includes:

1. **LocalAI multi-modal integration** (motivated by [Richard Palethorpe's LinkedIn post](https://www.linkedin.com/posts/richiejp_in-the-last-6-months-we-have-created-17-c-ugcPost-7493675258240221185-ZZzU/) on 17 C++ inference backends)
2. **Tool system composability** — pipelines, typed schemas, retry
3. **LLM integration hardening** — provider ABC, native function calling, structured output
4. **Orchestrator improvements** — planner agent, feedback loops, state persistence
5. **Memory and session improvements** — semantic search, cross-family sharing
6. **DB and infra cleanup** — dual ORM elimination, indentation standardization, CI enforcement
7. **City architecture refinement** — job/workqueue unification, event dedup, service decomposition

Each section states the problem, the proposed change, affected files, and exit criteria.

---

## 2. LocalAI Multi-Modal Integration

### 2.1 Problem

Persola city agents currently operate in a single modality: text-in/text-out. The orchestrator's tool runner falls back to `memory_store` when the LLM doesn't emit structured tool calls, and the registered city tools (`workspace_write`, `run_python`, `emit_viz_event`) are text-only. Agents cannot perceive images, audio, or speech.

LocalAI's 17 C++ inference backends — covering LLMs, TTS (4 variants), ASR, speaker diarization, depth estimation, 3D reconstruction, object detection, face detection, sound classification, voice activity detection, privacy filtering, and noise suppression — provide a local, composable, zero-Python-runtime sensory layer that aligns with Persola's "local-first, chosen morals" thesis.

### 2.2 Changes

#### 2.2.1 LocalAI client (`persola/integrations/localai.py`)

New module alongside `llm.py`. Wraps LocalAI's REST API (which exposes the C++ backends). Implements the same informal interface as `OllamaClient` (`is_available`, `generate`, `chat`, plus modality-specific methods).

```
class LocalAIClient:
    def __init__(self, base_url, model, ...)
    def is_available(self) -> bool
    async def generate(self, prompt) -> str
    async def chat(self, messages, system_prompt) -> str
    async def transcribe(self, audio_path) -> dict          # moss-transcribe
    async def detect_voice(self, audio_path) -> dict         # voice-detect
    async def text_to_speech(self, text, voice) -> bytes     # moss-tts / magpie-tts
    async def detect_objects(self, image_path) -> dict       # rf-detr
    async def estimate_depth(self, image_path) -> bytes      # depth-anything
    async def locate(self, image_path, query) -> dict        # locate-anything
    async def detect_faces(self, image_path) -> dict         # face-detect
    async def classify_sound(self, audio_path) -> dict       # ced
    async def filter_privacy(self, text) -> dict             # privacy-filter
    async def denoise(self, audio_path) -> bytes             # LocalVQE
```

Register in `PersolaLLM._initialize_provider` as `"localai"` provider type. Gate behind `LOCALAI_URL` env var (no-op when unset).

**Files:** new `persola/integrations/localai.py`, edit `persola/integrations/llm.py`

#### 2.2.2 Multi-modal tool specs (`persola/orchestration/tools.py`)

Extend `ToolSpec` with optional input/output type declarations:

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    parallel_safe: bool = True
    tags: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None   # JSON Schema for args
    output_schema: Optional[Dict[str, Any]] = None   # JSON Schema for result
    modality: Optional[str] = None                    # "text" | "audio" | "image" | "binary"
```

This lets the orchestrator and UI understand what each tool expects and returns without inspecting handler internals.

**Files:** edit `persola/orchestration/tools.py`

#### 2.2.3 Tool pipelines (`persola/orchestration/pipelines.py`)

New module. A `ToolPipeline` chains tool outputs → downstream tool inputs as a directed acyclic graph (DAG). Inspired by LocalAI's composability pattern (e.g. `voice-detect → moss-transcribe → privacy-filter → LocalVQE`).

```python
@dataclass
class PipelineStep:
    tool_name: str
    input_mapping: Dict[str, str]  # "arg_name": "previous_step.result.field"
    args: Optional[Dict[str, Any]] = None  # static overrides

@dataclass
class ToolPipeline:
    name: str
    steps: List[PipelineStep]
    description: str = ""

class PipelineExecutor:
    async def run(self, pipeline: ToolPipeline, initial_args: Dict[str, Any]) -> List[Dict[str, Any]]
```

Register pipelines as first-class citizens in the `ToolRegistry` alongside individual tools. The city pulse and conductor can invoke pipelines (e.g. "hear and summarize" = `voice_detect → transcribe → privacy_filter → delegate_subtask`).

**Files:** new `persola/orchestration/pipelines.py`, edit `tools.py` to support pipeline registration

#### 2.2.4 Multi-modal city tools (`persola/orchestration/city_tools.py`)

Register LocalAI-backed tools in the city tool registry:

| Tool | Backend | Purpose |
|------|---------|---------|
| `listen` | voice-detect + moss-transcribe | Transcribe audio input |
| `speak` | moss-tts | Generate speech from text |
| `see` | depth-anything + rf-detr | Perceive objects/depth in images |
| `locate` | locate-anything | Natural-language spatial queries |
| `anonymize` | privacy-filter | Redact PII before storage/transit |
| `denoise_audio` | LocalVQE | Clean speech audio |

These tools register into the city tool registry alongside `workspace_write` and `run_python`.

**Files:** edit `persola/orchestration/city_tools.py`, `persola/services/city_service.py` (tool tag mapping)

### 2.3 Exit Criteria

- `POST /api/v1/city/jobs/{id}/enqueue` with a `listen` tool call transcribes audio → stores artifact → emits `artifact.written` event.
- Pipeline executor runs a 3-step chain and returns per-step results.
- `PersolaLLM(provider="localai")` initializes when `LOCALAI_URL` is set.
- All existing tests pass (no regressions).

---

## 3. Tool System Composability

### 3.1 Problem

The tool system has several gaps:

1. **No typed schemas** — `ToolHandler = Callable[..., Awaitable[Dict[str, Any]]]` is untyped; args are `**kwargs` with no validation.
2. **No retry/backoff** — a tool failure is immediate; no retry for transient errors.
3. **No result caching** — `workspace_read` hits the DB every time even for unchanged artifacts.
4. **No pipeline composability** — covered in §2.2.3 above.
5. **Fallback tool behavior** — `team.py:81–94` silently converts LLM output to `memory_store` when no structured tool calls are parsed. This hides tool-calling failures from the operator.

### 3.2 Changes

#### 3.2.1 Tool input validation (`persola/orchestration/tools.py`)

Add optional `input_schema` (JSON Schema) to `ToolSpec`. When present, validate `**kwargs` against it before calling the handler. On validation failure, return `{"error": "invalid_args", "details": [...]}` instead of crashing.

**Files:** edit `persola/orchestration/tools.py`

#### 3.2.2 Tool retry decorator (`persola/orchestration/tools.py`)

Add `retries: int = 0` and `retry_delay_s: float = 1.0` fields to `ToolSpec`. The `ParallelToolExecutor.run_one` wraps the handler call in a simple retry loop for transient failures (connection errors, timeouts). Non-transient errors (validation, auth) are not retried.

**Files:** edit `persola/orchestration/tools.py`, `persola/orchestration/parallel.py`

#### 3.2.3 Tool result caching (`persola/orchestration/tools.py`)

Add `cache_ttl_s: Optional[float] = None` to `ToolSpec`. When set, cache the last result keyed by `json.dumps(args, sort_keys=True)`. Subsequent calls with identical args return the cached result until TTL expires. Useful for `workspace_read`, `memory_recall`, `cyrex_status`.

**Files:** edit `persola/orchestration/tools.py`

#### 3.2.4 Tool-calling fallback transparency (`persola/orchestration/team.py`)

When the LLM output contains no parseable tool calls, instead of silently creating a `memory_store` call, emit an audit event (`AuditEventType.TOOL_CALL` with `detail: {"fallback": true, "raw_output": ...}`) and still store to memory. This makes the fallback observable without changing behavior.

**Files:** edit `persola/orchestration/team.py`

### 3.3 Exit Criteria

- Tool with `input_schema` rejects invalid args with structured error.
- Tool with `retries=3` retries on timeout before failing.
- `workspace_read` with `cache_ttl_s=5.0` returns cached result within TTL.
- Audit log shows `tool_call` events with `fallback: true` when LLM omits structured calls.
- All existing tests pass.

---

## 4. LLM Integration Hardening

### 4.1 Problem

The five LLM provider clients (`OllamaClient`, `OpenAICompatibleClient`, `AnthropicClientWrapper`, `GeminiClient`) share no formal interface. Each implements `is_available`, `generate`, and `chat` ad-hoc. Key gaps:

1. **No ABC** — adding a new provider requires reading all existing clients to match the informal contract.
2. **No native function/tool calling** — the orchestrator parses LLM text output with regex (`tool_calls.py`) instead of using providers' native function-calling APIs (OpenAI, Anthropic, Gemini all support this).
3. **No structured/JSON output mode** — `PersonaEngine` builds system prompts asking for JSON, but there's no `response_format` enforcement.
4. **Streaming inconsistency** — only `OllamaClient` has `generate_streaming`; others fall back to non-streaming.
5. **No model routing** — the team orchestrator uses the same model for all specialist roles. City scale docs recommend cheaper models for children but there's no routing mechanism.

### 4.2 Changes

#### 4.2.1 LLM provider ABC (`persola/integrations/llm.py`)

Extract a formal `LLMProvider` protocol/ABC:

```python
class LLMProvider(Protocol):
    def is_available(self) -> bool: ...
    async def generate(self, prompt: str) -> str: ...
    async def chat(self, messages: list[dict], system_prompt: str = "") -> str: ...
    async def generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]: ...
```

Make all five clients implement it. `PersolaLLM` wraps any `LLMProvider`.

**Files:** edit `persola/integrations/llm.py`

#### 4.2.2 Native function calling (`persola/integrations/llm.py`, `persola/orchestration/tool_calls.py`)

Add `supports_tool_calling() -> bool` to the ABC. When true, the orchestrator sends tool definitions as part of the chat request instead of relying on text parsing. Providers that support it:

- `OllamaClient` — Ollama supports tool calling via `/api/chat` with `tools` parameter
- `OpenAICompatibleClient` — native `tools` parameter in chat completions
- `AnthropicClientWrapper` — native `tools` parameter
- `GeminiClient` — `function_declarations` in `generationConfig`

When `supports_tool_calling()` is true, skip the regex parser and use the provider's native response format. When false, fall back to `tool_calls.py`.

**Files:** edit `persola/integrations/llm.py`, `persola/orchestration/tool_calls.py`, `persola/orchestration/team.py`

#### 4.2.3 Structured output mode (`persola/integrations/llm.py`)

Add `generate_structured(self, prompt, schema) -> dict` to the ABC. Uses `response_format` (OpenAI/Gemini) or system prompt enforcement (Ollama/Anthropic) to guarantee valid JSON output matching a schema.

**Files:** edit `persola/integrations/llm.py`

#### 4.2.4 Model routing for team roles (`persola/orchestration/team.py`)

Add optional `model_for_role: Optional[Callable[[str], str]]` to `TeamOrchestrator`. When set, the coordinator role uses the primary model while specialist roles use a cheaper model. City scale docs recommend `llama3:70b` for parents/coordinators and `llama3:8b` for children.

Default implementation: coordinator → current model, specialists → current model (no change). City service overrides with the family's model tier policy.

**Files:** edit `persola/orchestration/team.py`, `persola/services/city_service.py`

### 4.3 Exit Criteria

- All five providers satisfy `LLMProvider` protocol.
- OpenAI provider sends tool definitions; response returns parsed tool calls without regex.
- `generate_structured(prompt, schema)` returns valid JSON matching schema.
- Coordinator uses `llama3:70b`, specialists use `llama3:8b` when model routing is configured.
- All existing tests pass.

---

## 5. Orchestrator Improvements

### 5.1 Problem

1. **Keyword-matching router** — `router.py` selects specialists by counting keyword overlaps in the task text. This is brittle and doesn't use LLM reasoning for planning.
2. **No planner agent** — the coordinator receives specialist outputs but doesn't generate a decomposition plan beforehand.
3. **WorkflowState is in-memory only** — `state.py:WorkflowState` is a dataclass that never persists to DB. On server restart, all workflow history is lost.
4. **No tool-call feedback loop** — when a tool fails, the orchestrator doesn't retry with corrected args or report the failure back to the LLM for re-planning.
5. **TeamSessionState is ephemeral** — `state.py:TeamSessionState` lives only in the `_run_langgraph_path` / `_run_chain_path` call frame. Multi-turn conversations across API calls lose context.

### 5.2 Changes

#### 5.2.1 LLM-assisted planner (`persola/orchestration/planner.py`)

New module. When LLM is available, the coordinator generates a structured delegation plan instead of using keyword matching:

```
Task → Coordinator LLM → JSON plan:
{
    "analysis": "task needs data analysis and creative output",
    "specialists": ["analyst", "creative"],
    "sequence": ["analyst:analyze data", "creative:design output based on analysis"],
    "synthesis_prompt": "Combine analysis and design into..."
}
```

Fall back to the existing keyword router when LLM is unavailable.

**Files:** new `persola/orchestration/planner.py`, edit `persola/orchestration/team.py`

#### 5.2.2 Tool-call feedback loop (`persola/orchestration/team.py`)

When a tool call fails, append the failure to the LLM context and re-invoke with the error information:

```
Specialist output → tool calls → some fail →
    "The following tools failed: [{name, error}]. Please revise your approach."
    → re-invoke specialist with error context → new tool calls
```

Cap at 2 retries to prevent loops.

**Files:** edit `persola/orchestration/team.py`, `persola/orchestration/parallel.py`

#### 5.2.3 Workflow state persistence (`persola/orchestration/state.py`, `persola/db/models.py`)

Persist `WorkflowState` and `TeamSessionState` to DB. Add a new Alembic migration with:

- `team_workflow_runs` table: `workflow_id`, `team_id`, `session_id`, `goal`, `status`, `runtime_mode`, `created_at`, `completed_at`, `result_summary`
- `team_workflow_step_runs` table: `step_id`, `workflow_id`, `role`, `task`, `output`, `tool_calls` (JSONB), `started_at`, `completed_at`

This enables multi-turn conversations (resume a session by ID) and post-hoc analysis of team runs.

**Files:** new migration, `persola/db/models.py`, `persola/orchestration/state.py`

#### 5.2.4 Session persistence for multi-turn (`persola/services/team_service.py`)

Persist `TeamSessionState.messages` to the existing `sessions` / `messages` tables so multi-turn conversations survive restarts. The `TeamOrchestrator.run` method loads prior messages when a `session_id` is provided.

**Files:** edit `persola/services/team_service.py`, `persola/orchestration/team.py`

### 5.3 Exit Criteria

- Coordinator generates structured JSON plan when LLM is available; falls back to keyword router.
- Failed tool call triggers one re-invocation with error context.
- `WorkflowState` persists to DB; queryable via API.
- Multi-turn conversation resumes from DB after server restart.
- All existing tests pass.

---

## 6. Memory and Session Improvements

### 6.1 Problem

1. **In-memory MemoryStore loses state on restart** — `memory.py:GLOBAL_MEMORY` is a process-local dict.
2. **Redis memory has no per-key TTL** — only the session hash has a 24h expiry.
3. **No semantic search** — `search()` is substring matching; no embeddings/vector search.
4. **Memory not shared across families** — city family members have separate memory scopes.
5. **Memory not integrated with DB** — team memory (`team_memory` table) and in-memory `MemoryStore` are separate systems.

### 6.2 Changes

#### 6.2.1 DB-backed memory fallback (`persola/orchestration/memory.py`)

When Redis is unavailable, fall back to the `team_memory` DB table (already exists in schema) instead of the in-memory dict. This ensures memory survives restarts without requiring Redis.

**Files:** edit `persola/orchestration/memory.py`, `persola/orchestration/tool_loader.py`

#### 6.2.2 Per-key TTL for Redis memory (`persola/orchestration/redis_memory.py`)

Add optional `ttl_seconds` parameter to `RedisTeamMemory.store()`. Use Redis `SETEX` per field instead of hash-level expiry. Default: 7 days.

**Files:** edit `persola/orchestration/redis_memory.py`

#### 6.2.3 Semantic search stub (`persola/orchestration/memory.py`)

Add `search_semantic(query, embedding_fn, limit)` that accepts an optional embedding function. When provided, compute cosine similarity between query embedding and stored value embeddings. When not provided, fall back to substring match. This prepares the API for future vector integration (pgvector or Milvus) without requiring it now.

**Files:** edit `persola/orchestration/memory.py`

#### 6.2.4 Cross-family memory sharing for city jobs (`persola/services/city_service.py`)

When a city job is active, all family members share a common memory scope keyed by `job_id`. The tool loader creates a memory scope per job, not per session.

**Files:** edit `persola/services/city_service.py`, `persola/orchestration/tool_loader.py`

### 6.3 Exit Criteria

- Memory tool works without Redis (DB fallback).
- Redis memory per-key TTL configurable.
- `search_semantic` returns ranked results when embedding function provided; substring results otherwise.
- Family members on the same job share memory scope.
- All existing tests pass.

---

## 7. DB and Infra Cleanup

### 7.1 Problem

1. **Dual ORM (resolved but not enforced)** — `tables.py` is deprecated and aliased, but there's no lint rule or CI check preventing new imports from it.
2. **Mixed indentation** — orchestration/db files use tabs; api/analysis/tests use 4 spaces. No formatter enforces consistency per-file.
3. **Missing eslint config** — `npm run lint` fails out-of-the-box (no `eslint.config.*`).
4. **80% coverage gate not enforced** — `pyproject.toml` has `fail_under = 80` but no CI job runs it.
5. **`BaseRepository` lacks async commit** — `create`/`update` flush but don't commit; callers must remember to commit.
6. **No connection pool monitoring** — no visibility into DB connection health.

### 7.2 Changes

#### 7.2.1 Deprecation guard (`pyproject.toml`, CI)

Add a `ruff` rule `F401` + `per-file-ignores` to flag `from persola.db.tables import` in any file outside `persola/db/tables.py` itself. Run as part of lint.

**Files:** edit `pyproject.toml`, CI workflow

#### 7.2.2 Indentation standardization

Adopt 4-space indentation everywhere (matching Black/Ruff defaults). The existing mixed tabs in `db/models.py`, `orchestration/task_queue.py`, `orchestration/daemon.py`, `orchestration/org_chart.py`, `orchestration/audit_log.py`, `tests/conftest.py` are converted. Use `ruff format` to enforce.

**Files:** all files in `persola/db/`, `persola/orchestration/` (tabs → 4 spaces)

#### 7.2.3 ESLint config (`ui/eslint.config.js`)

Create a minimal `eslint.config.js` for ESLint v9 flat config format. Extend `@eslint/js` recommended + `typescript-eslint` + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`. Fix any lint errors.

**Files:** new `ui/eslint.config.js`, fix lint errors in `ui/src/`

#### 7.2.4 CI enforcement (`.github/workflows/`)

Add a CI workflow that runs:
- `ruff check .` and `ruff format --check .`
- `pytest --cov=persola --cov-fail-under=80`
- `npm run lint` and `npm run build` in `ui/`

**Files:** new `.github/workflows/ci.yml`

#### 7.2.5 Repository commit helper (`persola/db/repositories/base.py`)

Add an optional `commit: bool = False` parameter to `BaseRepository.create` and `BaseRepository.update`. When true, commit after flush. Document the convention: repositories flush by default; callers own the transaction unless `commit=True`.

**Files:** edit `persola/db/repositories/base.py`

#### 7.2.6 DB pool health check (`persola/db/database.py`)

Add a `pool_status()` function that returns `pool.size()`, `pool.checkedout()`, `pool.checkedin()` from the async engine. Expose via `GET /health/db` endpoint.

**Files:** edit `persola/db/database.py`, `persola/api/main.py`

### 7.3 Exit Criteria

- `from persola.db.tables import` triggers ruff warning outside `tables.py`.
- `ruff format .` produces zero changes (all files already formatted).
- `npm run lint` passes with zero warnings.
- CI workflow runs and gates on all three checks.
- `GET /health/db` returns pool status.
- All existing tests pass.

---

## 8. City Architecture Refinement

### 8.1 Problem

1. **City jobs and workqueue overlap** — `city_jobs` (family-scoped, goal-oriented) and `work_tasks` (team-scoped, role-addressed) serve overlapping purposes. A city job's execution is driven by the city pulse/conductor, while workqueue tasks are driven by the daemon. There's no formal bridge.
2. **No event deduplication** — `city_events` has no unique constraint on `(event_type, payload)`. Duplicate events can be emitted on retries.
3. **No event replay** — events are append-only with no replay mechanism for debugging or visualization restart.
4. **City service is monolithic** — `city_service.py` is 2809 lines handling families, jobs, commons, events, life cycle, pulse, conductor, scale, memorial, chronicle, generation.
5. **No rate limiting per-family** — the city's in-memory token bucket is global, not per-family. One family can starve others.

### 8.2 Changes

#### 8.2.1 City job ↔ workqueue bridge (`persola/services/city_service.py`, `persola/orchestration/daemon.py`)

When a city job starts, the conductor creates a workqueue task for each family member's role. The daemon picks up these tasks and runs the orchestrator. When all tasks complete, the job is marked completed. This unifies the two systems:

```
City Job → conductor → workqueue tasks (per role) → daemon → orchestrator → results → job complete
```

The workqueue task's `session_id` links back to the city job ID. The city pulse/conductor becomes the planner; the daemon becomes the executor.

**Files:** edit `persola/services/city_service.py`, `persola/orchestration/daemon.py`, `persola/api/city.py`

#### 8.2.2 Event dedup (`persola/db/models.py`, `persola/services/city_service.py`)

Add a `dedup_key` column to `city_events` (nullable, SHA-256 of `event_type + sorted(payload)`). On insert, check for existing `dedup_key` within a 5-second window. Skip duplicate.

**Files:** new migration, `persola/db/models.py`, `persola/services/city_service.py`

#### 8.2.3 Event replay endpoint (`persola/api/city.py`)

Add `POST /api/v1/city/events/replay?since={timestamp}&event_type={type}` that re-emits events matching the filter. Useful for visualization restart or debugging.

**Files:** edit `persola/api/city.py`

#### 8.2.4 City service decomposition

Split `city_service.py` (2809 lines) into focused modules:

| Module | Responsibility |
|--------|---------------|
| `city_service.py` | Families, lineage, spawn |
| `city_job_service.py` | Jobs, artifacts, runs |
| `city_event_service.py` | Events, SSE, replay |
| `city_life_service.py` | Aging, death, succession, legacy |
| `city_pulse_service.py` | Pulse, conductor, district routing |
| `city_scale_service.py` | Scale probe, awaken, metrics |

**Files:** split `persola/services/city_service.py` into 6 modules, update imports

#### 8.2.5 Per-family rate limiting (`persola/api/city.py`)

Replace the global token bucket with a per-family bucket. Each family gets `capacity=10, refill_rate=0.5`. The family ID is extracted from the request path or body.

**Files:** edit `persola/api/city.py`, `persola/cache.py`

### 8.3 Exit Criteria

- City job completion requires all workqueue tasks to finish.
- Duplicate events are silently dropped within 5s window.
- `POST /city/events/replay` returns matching events.
- `city_service.py` is under 500 lines.
- One family cannot exceed 10 requests/second.
- All existing tests pass.

---

## 9. Implementation Sequencing

### Tier 1 — Quick Wins (1–2 days each)

| Item | Section | Risk |
|------|---------|------|
| LLM provider ABC | §4.2.1 | Low |
| Indentation standardization | §7.2.2 | Low (formatter) |
| ESLint config | §7.2.3 | Low |
| Deprecation guard | §7.2.1 | Low |
| Tool input validation | §3.2.1 | Low |
| Tool retry decorator | §3.2.2 | Low |
| Tool-calling fallback transparency | §3.2.4 | Low |
| Per-key TTL for Redis | §6.2.2 | Low |
| DB pool health check | §7.2.6 | Low |

### Tier 2 — Core Improvements (3–5 days each)

| Item | Section | Risk |
|------|---------|------|
| LocalAI client | §2.2.1 | Medium (new integration) |
| Native function calling | §4.2.2 | Medium (provider-specific) |
| Structured output mode | §4.2.3 | Medium |
| Model routing | §4.2.4 | Low |
| Tool result caching | §3.2.3 | Low |
| DB-backed memory fallback | §6.2.1 | Low |
| Semantic search stub | §6.2.3 | Medium |
| CI enforcement | §7.2.4 | Low |
| Repository commit helper | §7.2.5 | Low |

### Tier 3 — Architectural Changes (1–2 weeks each)

| Item | Section | Risk |
|------|---------|------|
| Tool pipelines | §2.2.3 | Medium (new abstraction) |
| Multi-modal city tools | §2.2.4 | Medium (depends on LocalAI) |
| LLM-assisted planner | §5.2.1 | Medium |
| Tool-call feedback loop | §5.2.2 | Medium |
| Workflow state persistence | §5.2.3 | Medium (new migration) |
| Session persistence | §5.2.4 | Medium |
| City job ↔ workqueue bridge | §8.2.1 | High (core flow change) |
| City service decomposition | §8.2.4 | Medium (large refactor) |

### Tier 4 — Infrastructure (parallel with above)

| Item | Section | Risk |
|------|---------|------|
| Event dedup | §8.2.2 | Low |
| Event replay | §8.2.3 | Low |
| Per-family rate limiting | §8.2.5 | Low |
| Cross-family memory sharing | §6.2.4 | Low |

---

## 10. Dependencies and Risks

| Risk | Mitigation |
|------|------------|
| LocalAI API surface changes | Pin to specific LocalAI version; wrap all calls behind adapter |
| Native function calling inconsistency across providers | Fall back to text parsing when provider doesn't support tools |
| Workflow state migration conflicts with existing 006 | Use `down_revision="006_workqueue"` for new migration |
| City service decomposition breaks imports | Use `__init__.py` re-exports for backward compatibility |
| Tool pipelines add complexity | Start with linear chains only; DAG support is a future extension |
| Mixed indentation conversion may break `git blame` | Use `git blame --ignore-rev` with the formatting commit |
| 80% coverage gate blocks CI on pre-existing gaps | Run coverage locally first; fix gaps before enabling gate |

---

## 11. Success Definition

This optimization plan is validated when:

1. A city agent can perceive multi-modal input (audio/image) via LocalAI backends.
2. Tool pipelines compose 3+ tools in sequence with automatic data flow.
3. The LLM provider layer is extensible with a formal protocol.
4. Native function calling works for OpenAI/Ollama providers (no regex parsing).
5. Workflow state survives server restarts.
6. The codebase has zero mixed-indentation files and passes `ruff format --check`.
7. `npm run lint` passes.
8. CI enforces lint + type + test + coverage gates.
9. `city_service.py` is under 500 lines.
10. All 282+ existing tests pass with no regressions.
