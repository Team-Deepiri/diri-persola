# Schema Integration Map — Personality Framework → Communal City

**Audience:** engineers picking up PR [#46](https://github.com/Team-Deepiri/diri-persola/pull/46) as the direction reference  
**Question:** Does the product rebrand (personality tuner → society / communal city layer) change **immediate schema integration**?  
**Answer: Yes.** New tables, repos, APIs, and Alembic head are required. Existing persona/agent/team schema stays; city schema **extends** it.

**Reference points:**
- Current `main` README framing: *Agentic Personality Framework* (personas, knobs, Cyrex spawn)
- Direction docs: [COMMUNAL_CITY_DESIGN.md](./COMMUNAL_CITY_DESIGN.md), [COMMUNAL_CITY_ROADMAP.md](./COMMUNAL_CITY_ROADMAP.md)
- Prior DB plan: [DB_IMPLEMENTATION.md](./DB_IMPLEMENTATION.md) (personas/agents baseline — still valid, incomplete for city)

---

## 1. What “rebrand” means here

| Layer | Before (main README) | After (city direction) |
|-------|----------------------|------------------------|
| Product identity | Personality framework + playground | **Society layer**: families, commons, build+run, ~100 agents, Austin viz |
| Primary entities | `personas`, `agents`, sessions | + `families`, `family_members`, `city_jobs`, commons, `city_events` |
| Runtime surface | `/api/v1/personas`, `/agents`, teams | + `/api/v1/city/*` |
| Persistence | Alembic `001`–`003` | + **`004_communal_city`** (required for city) |
| Optional sync | Cyrex persona push | Unchanged; city bulk sync is additive |

Immediate schema integration **must** land `004` and wire services to `persola.db.models` — not to the legacy `tables.py` rows.

---

## 2. Does it change immediate schema work?

| Concern | Change? | Detail |
|---------|---------|--------|
| Persona / agent columns | **No** (for Phase 1) | Reuse `agents.id`, `personas.id`; city adds FKs |
| Team tables (`team_*`) | **No replace** | City jobs may link `team_session_id`; keep team orchestration |
| New tables | **Yes** | Six city tables in `004_communal_city` |
| Alembic head | **Yes** | Deploy path: `alembic upgrade head` must include `004` |
| Active ORM | **Resolved** | Canonical: `persola/db/models.py` + Alembic. Legacy `tables.py` is a deprecated alias; `repo.py` wraps `PersonaRepository` / `AgentRepository`. |
| Docker / `persola-db` | **No structural change** | Same Postgres service; schema version advances |
| UI | Additive | `CityView` + city API client; Team Workbench stays |

---

## 3. Exact repo structural change (as-shipped on PR branch)

```text
diri-persola/
├── alembic/versions/
│   ├── 001_initial_schema.py          # personas, agents, …
│   ├── 002_expanded_runtime_models.py
│   ├── 003_team_orchestration.py      # team_*
│   └── 004_communal_city.py           # NEW — city schema (required)
│   └── 005_city_life_cycle.py         # NEW — age/goals/death/generation
├── persola/
│   ├── db/
│   │   ├── models.py                  # EXTEND — Family*, City*, Workspace*
│   │   ├── tables.py                  # LEGACY — leave alone for city
│   │   ├── repo.py                    # still uses tables.py (persona/agent)
│   │   └── repositories/
│   │       └── city_repository.py     # NEW
│   ├── api/
│   │   ├── main.py                    # include city router
│   │   └── city.py                    # NEW — /api/v1/city/*
│   ├── services/
│   │   └── city_service.py            # NEW
│   └── orchestration/
│       ├── city_tools.py              # workspace_* / run_python
│       ├── sandbox.py
│       ├── city_worker.py / city_pulse.py / city_scale.py / …
│       └── commons_mirror.py          # disk commons (Phase 9)
├── ui/src/
│   ├── api/index.ts                   # city client methods
│   └── components/CityView/           # NEW
├── tests/integration/
│   ├── test_city_api.py
│   └── test_city_phase*.py
└── docs/
    ├── COMMUNAL_CITY_DESIGN.md
    ├── COMMUNAL_CITY_ROADMAP.md
    ├── CITY_EVENTS.md
    ├── CITY_SCALE.md
    └── SCHEMA_INTEGRATION_REBRAND_MAP.md  # this file
```

### Schema objects added by `004_communal_city`

| Table | Role |
|-------|------|
| `families` | Lineage root, district, policy JSON |
| `family_members` | Links `agents`, parent/child, knobs/tools |
| `city_jobs` | Family work unit; optional `team_session_id` |
| `workspace_artifacts` | Commons files (path/content/version) |
| `workspace_runs` | Tool execution records |
| `city_events` | Austin/event contract feed (`event_type` + JSONB payload) |

FK spine: `family_members.agent_id → agents.id` (and thus personas via agent). Do not fork a parallel agent identity for city.

---

## 4. README comparison (what Joel should diff)

| Topic | `main` README | City direction (PR #46 branch) |
|-------|---------------|--------------------------------|
| Tagline | Agentic Personality Framework | Same + **Communal City** feature line |
| Install / CLI / personas API | Unchanged | Unchanged |
| City APIs | Absent | `/api/v1/city/...` (families, jobs, pulse, heartbeat, conduct, Austin export) |
| Design links | Absent / thin | `docs/COMMUNAL_CITY_*.md`, events, scale |
| Schema story | Implied personas/agents | Explicit: run migrations through **`004`** |

**Integration rule:** keep personality README flows working; city is a **new vertical**, not a rename of persona endpoints.

---

## 5. Limiting factors (production)

1. **Dual ORM** — `tables.py` vs `models.py`. Alembic + city + teams use `models.Base`. Immediate work: city only on `models.py`; plan a later consolidation of `repo.py` off `tables.py`.
2. **Migration order** — City requires `003` (teams) then `004`. Fresh envs: `alembic upgrade head`.
3. **Privileges / sandbox** — `run_python` / workspace paths are app-level constraints, not DB schema; schema stores outcomes only.
4. **Event contract** — Viz (Austin) consumes `city_events` shape in [CITY_EVENTS.md](./CITY_EVENTS.md); changing event types is a contract change, not a table rename.
5. **Scale** — ~100 agents are rows + workers; no sharding in Phase 1–10. Indexes on `family_id`, `job_id`, `created_at` matter more than new databases.
6. **Cyrex** — Optional; schema does not block offline city demos.

---

## 6. Production-oriented start sequence

1. `docker compose up` / ensure `persola-db` healthy.
2. `alembic upgrade head` → confirm `004_communal_city` applied.
3. Smoke: `POST /api/v1/city/families` → spawn → job → `GET /api/v1/city/events`.
4. Do **not** recreate personas/agents tables for city.
5. Prefer service layer (`CityService`) over raw SQL; keep event emission on every state change for Austin.

---

## 7. Out of scope for “immediate” schema integration

- Renaming the Python package or HTTP prefix (`/api/v1/personas` stays).
- Dropping team tables or Team Workbench.
- Merging `tables.py` into `models.py` (follow-up tech debt).
- DescentDefense / other product rebrands — unrelated to this repo.

---

## 8. Status on this branch

Phases **0–10** implemented against this map (schema + APIs + UI + conductor).  
PR description may still say “Phase 1 only” — treat this file + roadmap checklist as source of truth until the PR body is refreshed.
