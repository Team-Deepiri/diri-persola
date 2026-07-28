# Persola Communal City — Full Implementation Roadmap

**Status:** Implemented (Phases 0–13)  
**Depends on:** [COMMUNAL_CITY_DESIGN.md](./COMMUNAL_CITY_DESIGN.md)  
**Baseline:** Persola personality engine + team orchestration (LangGraph, Team Workbench) already in repo

---

## 1. Roadmap overview

Ship Persola from “team of five personalities” to a **communal agent city** that builds and runs artifacts, in five phases. Each phase leaves a deployable, testable milestone.

```text
Phase 0  Vision locked (this doc pair)
    │
Phase 1  Families + Commons + City APIs
    │
Phase 2  Build/run tools + orchestrator wiring
    │
Phase 3  Wedge demo (one family, one job, City UI mode)
    │
Phase 4  City visualization + Austin event contract
    │
Phase 5  Scale toward ~100 agents (workers, districts, metrics)
    │
Phase 6  Prove 100+ distinct personalities + interactive city viz
    │
Phase 7  City pulse — multi-district work + parent cohesion gate
    │
Phase 8  Living heartbeat — multi-contributor pulse + auto-tick
    │
Phase 9  Austin export pack + disk commons + cinema demo
    │
Phase 10 City conductor — LLM team-invoke across families
    │
Phase 11 Memorial + prod ops — era roll, life metrics, Cyrex living sync, ASGI workers
    │
Phase 12 Chronicle + Austin stream — era timeline, life SSE filters, city health, compose fix
    │
Phase 13 Era chamber — generation proof, cohesion UI, goals/dreams policy
```

---

## 2. Current baseline (do not rebuild)

Already present and should be extended, not replaced:

| Area | Location |
|------|----------|
| Persona knobs / engine | `persola/models.py`, `persola/engine.py` |
| Team orchestrator | `persola/orchestration/team.py` |
| Archetypes | `persola/orchestration/personalities.py` |
| Tool registry shell | `persola/orchestration/tools.py` |
| Team persistence | `persola/db/models.py` (`team_*` tables) |
| Team service / API | `persola/services/team_service.py`, `persola/api/teams.py` |
| UI | `ui/src/components/TeamWorkbench/` |
| Cyrex persona sync | `persola/integrations/cyrex.py` |

Prior platform phases (persistence, CLI, analysis, auth) remain in [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md). This roadmap is **Phase 8+** relative to that plan: communal city.

---

## 3. Phase 0 — Vision and docs

**Goal:** Shared language for society layer, families, commons, build+run, city viz.

| Deliverable | Owner signal |
|-------------|--------------|
| `docs/COMMUNAL_CITY_DESIGN.md` | Design locked |
| `docs/COMMUNAL_CITY_ROADMAP.md` | Sequencing locked |
| README pointer (optional follow-up) | Discoverability |

**Exit criteria:** Design + roadmap merged; Austin and builders can cite the same primitives.

---

## 4. Phase 1 — Data model and City APIs

**Goal:** Persist families, commons, jobs, and events. REST under `/api/v1/city/...`.

### 4.1 Schema

Add Alembic migration(s) for:

| Table | Purpose |
|-------|---------|
| `families` | Lineage root, name, policy JSON |
| `family_members` | agent_id, family_id, parent_member_id, role (`parent`/`child`), knob overrides, tool tags |
| `workspace_artifacts` | job_id, family_id, path, content/blob ref, created_by_agent_id, version |
| `workspace_runs` | job_id, tool, args, status, stdout/stderr, agent_id, duration_ms |
| `city_jobs` | family_id, goal, district, status, result, team_session_id (nullable FK) |
| `city_events` | job_id, event_type, payload JSONB, created_at |

### 4.2 Repositories / services

- New modules beside existing team repos (e.g. `persola/db/repositories/city_*.py`, `persola/services/city_service.py`).
- Keep team session models for orchestration continuity; city job may attach `team_session_id`.

### 4.3 API endpoints (minimum)

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/api/v1/city/families` | Create family + parent member |
| `POST` | `/api/v1/city/families/{id}/spawn` | Spawn child with inheritance |
| `GET` | `/api/v1/city/families/{id}` | Lineage graph |
| `POST` | `/api/v1/city/jobs` | Start job (goal, family_id, district) |
| `GET` | `/api/v1/city/jobs/{id}` | Status + summary |
| `GET` | `/api/v1/city/jobs/{id}/artifacts` | List commons files |
| `GET` | `/api/v1/city/jobs/{id}/runs` | List executions |
| `GET` | `/api/v1/city/jobs/{id}/events` | Event history |

### 4.4 Exit criteria

- `docker compose up` → create family → spawn child → restart → lineage still present.
- Job row creatable even before real tool execution (status `pending` / `planned`).

---

## 5. Phase 2 — Build/run tools and orchestrator wiring

**Goal:** Agents actually write and execute inside a sandboxed commons.

### 5.1 Tools

Register for city jobs (extend `ToolRegistry` / `tool_loader`):

| Tool | Notes |
|------|-------|
| `workspace_write` | Persist artifact; emit `artifact.written` |
| `workspace_read` | Read by path |
| `workspace_list` | List paths under job workspace |
| `run_python` | Subprocess or restricted exec; **no network**; timeout + output cap |
| `emit_viz_event` | Append validated `city_events` row |

### 5.2 Orchestrator changes

- Wire structured tool calls through `TeamOrchestrator` so the **executor** role invokes tools from a plan, not only post-hoc `memory_store` / `delegate_subtask`.
- Persist each invocation to `workspace_runs`.
- Enforce path sandbox rooted at job commons (reject `..` and absolute escapes).

### 5.3 Safety defaults

- `run_python`: deny outbound network; wall-clock timeout (e.g. 10–30s); stdout/stderr truncation.
- Concurrency: per-job and per-family caps.
- Audit: every run has agent_id + job_id.

### 5.4 Exit criteria

- Automated test: write file via tool → read back → run a trivial script → `workspace_runs.status == succeeded`.
- Failed sandbox escape attempts rejected.

---

## 6. Phase 3 — Wedge demo (shippable slice)

**Goal:** One vertical slice that *feels* like a living community — not 100 agents yet.

### 6.1 Scope

1. One family of **5–8 agents** (parent + children, distinct knobs/roles).
2. One shared commons (DB-backed artifacts; optional disk mirror).
3. One job type: **build a small artifact and run it** (e.g. generate Python + `run_python`, or viz JSON + stub render).
4. UI: extend Team Workbench with a **City** mode (roster, job start, artifact/run lists) — not a greenfield app.

### 6.2 Success criteria

| Check | Pass condition |
|-------|----------------|
| Cohesion | Operator starts job; multiple children contribute |
| Build | At least one artifact written to commons |
| Run | At least one successful `workspace_runs` entry |
| Observe | UI shows who built / who ran |
| Persist | Restart preserves job, artifacts, runs |

### 6.3 Explicit non-goals for the wedge

- Multi-tenant SaaS city hosting.
- Unrestricted shell.
- One hundred concurrent LLM agents.
- Replacing Cyrex.

---

## 7. Phase 4 — City visualization

**Goal:** Living graph + event feed; hand-off ready for Austin.

### 7.1 Product UI

- React city panel: nodes = agents, edges = family lineage, pulses = builds/runs.
- Live updates via SSE or WebSocket from `city_events` (polling acceptable for first cut).

### 7.2 Austin contract

Document and freeze event payload shapes (see design doc §12):

- `agent.spawned`
- `artifact.written`
- `run.started` / `run.finished`
- `job.started` / `job.completed`
- `cohesion.merge`

Publish as a short section in design doc or `docs/CITY_EVENTS.md` if the schema grows.

### 7.3 Exit criteria

- Demo job drives visible graph updates without refreshing the whole page (or with light poll ≤2s).
- External consumer can subscribe to the same event stream using the documented schema.

---

## 8. Phase 5 — Scale toward ~100 agents

**Goal:** Same primitives, higher concurrency and cheaper cohesion.

| Workstream | Direction |
|------------|-----------|
| Workers | Background job workers / queue for tool runs and LLM steps |
| Concurrency | Per-family and per-district limits; fair scheduling |
| Models | Cheaper/faster models for children; stronger model for parent/coordinator |
| Districts | Shard jobs by `build` / `viz` / `research` / `ops` |
| Metrics | Cohesion score, tool success rate, job latency histograms (`persola/metrics.py`) |
| Cyrex | Optional bulk spawn/sync when families leave Persola for platform runtime |

### 8.1 Exit criteria

- Sustained run of ≥50 agents across ≥5 families without unbounded memory growth.
- Documented path to 100 with known bottlenecks and mitigations.

---

## 8b. Phase 6 — Prove 100 + interactive visualization

**Goal:** A living city of **≥100 agents with unique personalities**, observable through an interactive district graph.

### 8b.1 Scale awaken

| Deliverable | Notes |
|-------------|-------|
| Distinct personalities | `city_personalities.py` — archetype baselines + index salts → unique fingerprints |
| `POST /api/v1/city/scale/awaken` | 10 families × 10 agents across build/viz/research/ops |
| `POST /api/v1/city/scale/probe` `mode=hundred` | Same as awaken; `mode=fifty` keeps Phase 5 bar |
| `GET /api/v1/city/snapshot` | Multi-family payload for the city UI |

### 8b.2 Interactive viz

| Deliverable | Notes |
|-------------|-------|
| District city graph | Four columns; family clusters; click-to-inspect personality traits |
| Live SSE | City UI prefers `EventSource` on `/events/stream` with poll fallback |
| Awaken control | **Awaken 100** button + progress to target |

### 8b.3 Exit criteria

- Probe reports `meets_hundred_bar` and `all_personalities_unique`.
- UI shows district layout, selectable agents with trait bars, live pulses.

---

## 8c. Phase 7 — City pulse + ecosystem cohesion

**Goal:** The awakened city *works* — families across districts execute personality-routed jobs; parents merge or veto; **ecosystems are visible** (goals, dreams, structured thinking, cohesion).

| Deliverable | Notes |
|-------------|-------|
| `POST /api/v1/city/pulse` | Each active family runs district-specific commons work |
| Personality routing | `city_pulse.py` picks executor/creative/analyst/… by district (**living only**) |
| `POST /jobs/{id}/cohesion/decide` | Parent `merge` / `veto` with `cohesion_min` policy |
| `GET /api/v1/city/ecosystem` | Family ecosystems: cohesion, goals/dreams, living/deceased, efficiency |
| Member life fields | goals, dreams, structured_thinking, growth, age (Alembic `005`) |
| Events | `city.pulse.*`, `cohesion.veto`, `life.aged` |
| UI | **Pulse city** + district filters + ecosystem vitals |

### 8c.1 Exit criteria

- Pulse across ≥4 families covers multiple districts with merge/veto decisions.
- Ecosystem payload exposes per-family cohesion + shared goals/dreams.
- Graph pulses update from pulse events; district filters hide/show columns.

---

## 8d. Phase 8 — Living heartbeat + generational death

**Goal:** The city keeps working; **death is natural**. Members age out; legacy (personality knobs, tools, goals, dreams, growth) passes to heirs so **efficiency does not collapse**.

| Deliverable | Notes |
|-------------|-------|
| Multi-contributor pulse | Support roles write notes; district lead builds/runs |
| `GET /api/v1/city/heartbeat` | Vitals + living/deceased + generation era + efficiency |
| `POST /api/v1/city/heartbeat/tick` | Life tick (age/death/succession) + pulse |
| `POST /api/v1/city/life/tick` | Explicit generational tick |
| Succession | `member.died` → `legacy.passed` → heir spawn (`successor_of_id`) |
| UI Heartbeat / **Generations** | Auto-tick; ghost nodes for deceased; G# badges |

### 8d.1 Exit criteria

- Pulse reports `avg_contributors ≥ 2` on seeded multi-role families.
- After forced aging past `max_age_ticks`, deaths spawn heirs and `efficiency_preserved` is true.
- Heartbeat tick returns vitals + life + pulse payloads.

---

## 8e. Phase 9 — Austin pack + disk commons + cinema

**Goal:** Hand Austin a self-contained viz pack; optionally mirror commons to disk; ship a one-click cinema demo.

| Deliverable | Notes |
|-------------|-------|
| `GET /api/v1/city/export/austin` | Graph nodes/edges, events, artifact samples, contract hints |
| Disk commons | `PERSOLA_CITY_COMMONS_ROOT` mirrors writes under `jobs/{id}/…` |
| `GET /api/v1/city/commons/status` | Mirror enabled + optional job file list |
| UI **Cinema** / **Export Austin** | Auto awaken+pulse+district spotlight; download JSON pack |

### 8e.1 Exit criteria

- Export pack has `pack_version`, graph, events, hints.
- With commons root set, artifact writes appear on disk.

---

## 8f. Phase 10 — City conductor

**Goal:** Cognitive conduction — families don’t only run scripted tools; when an LLM is available, TeamOrchestrator plans/builds against the commons.

| Deliverable | Notes |
|-------------|-------|
| `POST /api/v1/city/conduct` | Conduct N families; `use_llm` prefers TeamOrchestrator |
| Tool fallback | If no LLM, multi-contributor pulse tools still run (CI-safe) |
| Events | `city.conduct.started` / `city.conduct.finished` |
| UI **Conduct** | One-click conductor from City view |

### 8f.1 Exit criteria

- Conduct without LLM reports `mode=tools` and completes merge/veto.
- Conduct with stub/real LLM emits conduct events and returns team payload.

---

## 8g. Phase 11 — Memorial + production ops

**Goal:** Death remains visible; ops can run and sync the living city.

| Deliverable | Notes |
|-------------|-------|
| `GET /api/v1/city/memorial` | Deceased roll + heirs (legacy continuity) |
| Life Prometheus gauges | living / deceased / generation_max / efficiency / deaths / successions |
| `POST /api/v1/city/cyrex/sync` | City-wide Cyrex push (living-only, dry_run) |
| Family Cyrex sync | `living_only` + `dry_run` query flags; bounded concurrency |
| ASGI workers | `PERSOLA_WORKERS`; `docker-compose.prod.yml`; `persola-server` respects DEBUG |
| Cinema | Pulse → life tick → memorial in UI |

### 8g.1 Exit criteria

- Memorial lists deceased with at least one heir after life tick.
- Cyrex dry_run reports `would_sync` without network when configured flag is off / dry.
- Metrics helpers update after ecosystem / life tick.

---

## 8h. Phase 12 — Chronicle + Austin stream hardening

**Goal:** Austin (and operators) can follow the city's era as a timeline and stream life events city-wide.

| Deliverable | Notes |
|-------------|-------|
| `GET /api/v1/city/chronicle` | Era timeline; `life_only=true` filters death/legacy/spawn |
| `GET /api/v1/city/health` | Readiness: db + living/deceased + queue |
| SSE `city_wide` + `types=` | Stream without family_id; filter `member.died,legacy.passed,…` |
| Austin pack **v1.2** | Includes `chronicle` + life stream hints |
| Compose / Dockerfile | Repo-root build context; entrypoint auto-migrate; city healthcheck |

### 8h.1 Exit criteria

- Chronicle after life tick includes death/legacy events.
- City-wide SSE hello advertises `city_wide` + types.
- `GET /city/health` returns `ok: true` against test DB.

---

## 8i. Phase 13 — Era chamber + generation proof

**Goal:** Make the thesis visible and measurable — death is natural; productivity survives generations; families cohere by personality/goals/dreams.

| Deliverable | Notes |
|-------------|-------|
| `GET /api/v1/city/generations` | Cohorts, productivity_index, last_life_proof, continuity_ok |
| `PATCH /families/{id}/policy` | `max_age_ticks`, `cohesion_min` |
| `PATCH /members/{id}/life` | goals, dreams, structured_thinking |
| Austin pack **v1.3** | Includes `generations` |
| UI **Era chamber** | Generation bars, cohesion cards, chronicle, continuity pill |

### 8i.1 Exit criteria

- After life tick, generations report has legacy_edges ≥ 1 and last_life_proof.efficiency_preserved.
- Policy patch updates family.policy and living member max_age_ticks.
- Era chamber renders without breaking City view.

---

## 9. Suggested file / module layout

```text
persola/
  api/city.py                 # City REST routes
  services/city_service.py    # Families, jobs, commons orchestration
  orchestration/
    tools.py                  # Extend registry
    city_tools.py             # workspace_* + run_python handlers
    sandbox.py                # Path + process policy
  db/
    models.py                 # New city tables
    repositories/city_*.py
alembic/versions/00N_city_*.py
ui/src/components/CityView/   # Graph + event feed + City mode
docs/
  COMMUNAL_CITY_DESIGN.md
  COMMUNAL_CITY_ROADMAP.md
```

---

## 10. Testing strategy

| Layer | Focus |
|-------|-------|
| Unit | Inheritance of knobs/tool tags; path sandbox; event payload validation |
| Integration | Family spawn → job → write → run → events (Postgres) |
| API | City endpoints auth/rate-limit compatible with existing Phase 6 controls |
| UI smoke | City mode: start job, see artifact + run rows |
| Load (Phase 5) | Concurrent jobs / families; tool timeout behavior |

---

## 11. Dependencies and risks

| Risk | Mitigation |
|------|------------|
| LLM invents tool calls that never execute | Structured tool-call loop in orchestrator; tests on executor path |
| Unsafe `run_python` | Default deny network; timeout; no shell string concat; allowlist imports later if needed |
| Dual models (`tables.py` vs `db/models.py`) | New city tables go on the active SQLAlchemy models used by Alembic |
| Viz scope creep | Event schema first; Austin owns advanced visuals |
| Cost at 100 agents | Phase 5 model tiering + worker pool; do not scale before wedge |

---

## 12. Milestone checklist

- [x] **P0** Design + roadmap docs merged
- [x] **P1** City schema + `/api/v1/city` CRUD/lineage/jobs
- [x] **P2** `workspace_*` + sandboxed `run_python` + orchestrator tool calls
- [x] **P3** Wedge demo: one family builds and runs; UI City mode
- [x] **P4** City graph + live events; Austin contract documented
- [x] **P5** Scale path to ~100 with workers/districts/metrics
- [x] **P6** Prove ≥100 distinct personalities + interactive city visualization
- [x] **P7** City pulse + parent cohesion merge/veto + district filters
- [x] **P8** Living heartbeat — multi-contributor pulse + auto-tick
- [x] **P9** Austin export pack + disk commons mirror + cinema demo
- [x] **P10** City conductor — LLM team-invoke / tool fallback across families
- [x] **P11** Memorial + life metrics + Cyrex living sync + prod ASGI
- [x] **P12** Chronicle + city-wide life SSE + health + compose fix
- [x] **P13** Era chamber + generation continuity proof

---

## 13. Immediate next implementation step

Phases 0–13 are on the communal-city branch. Remaining:

1. Staging compose prod + Austin wiring to pack **v1.3** / generations / life SSE.
2. Real Cyrex keys: dry_run then `POST /city/cyrex/sync`.
3. Optional: operator edits for goals/dreams in inspect panel; remove deprecated `tables.py`.
