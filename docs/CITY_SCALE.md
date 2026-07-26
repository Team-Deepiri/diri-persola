# City Scale — Path to ~100 Agents (Phase 5)

**Status:** Implemented  
**Related:** [COMMUNAL_CITY_ROADMAP.md](./COMMUNAL_CITY_ROADMAP.md) §8 · [CITY_EVENTS.md](./CITY_EVENTS.md)

Persola keeps the same society primitives (families, commons, build/run) and adds concurrency governance, a worker pool, model tiers, district sharding, and metrics so the city can grow toward ~100 agents without unbounded fan-out.

---

## Defaults

| Knob | Env | Default |
|------|-----|---------|
| Global concurrent tool batches | `PERSOLA_CITY_MAX_GLOBAL` | 32 |
| Per-family concurrent | `PERSOLA_CITY_MAX_PER_FAMILY` | 8 |
| Per-district concurrent | `PERSOLA_CITY_MAX_PER_DISTRICT` | 16 |
| Per-job concurrent | `PERSOLA_CITY_MAX_PER_JOB` | 4 |
| Worker count | `PERSOLA_CITY_WORKERS` | 4 |
| Queue max | `PERSOLA_CITY_QUEUE_MAX` | 256 |
| Parent / coordinator model | `PERSOLA_CITY_PARENT_MODEL` | `llama3:70b` |
| Child model | `PERSOLA_CITY_CHILD_MODEL` | `llama3:8b` |

---

## Components

### ConcurrencyGovernor

Fair locks: **global ∩ family ∩ district ∩ job**. Prevents one family, district, or hot job from starving others.

### CityWorkerPool

In-process asyncio queue + N workers. Tool batches are enqueued via:

```http
POST /api/v1/city/jobs/{job_id}/enqueue
{"calls":[{"name":"workspace_write","args":{...}}], "agent_id":"...", "wait": false}
```

Set `"wait": true` to block until the worker finishes (tests / synchronous callers). Otherwise poll:

```http
GET /api/v1/city/workers/work/{work_id}
```

### Model tiers

On family create / child spawn:

- Parent / `coordinator` → parent model
- Children → child model

### District shards

Jobs carry `district` ∈ `build | viz | research | ops`. Governor + worker snapshots expose `district:{name}` shards.

### Metrics (Prometheus)

| Metric | Meaning |
|--------|---------|
| `persola_city_jobs_total{district,status}` | Job lifecycle |
| `persola_city_tool_runs_total{tool,status}` | Commons tool outcomes |
| `persola_city_job_duration_seconds{district}` | Batch latency histogram |
| `persola_city_cohesion_score` | Latest cohesion (0–1) |
| `persola_city_queue_depth` | Worker queue depth |
| `persola_city_active_agents` | Agents after scale probe |

### Cyrex bulk sync

```http
POST /api/v1/city/families/{family_id}/cyrex/sync
```

No-ops with `configured: false` when Cyrex env is unset.

---

## Scale probe

```http
POST /api/v1/city/scale/probe
{
  "mode": "fifty",
  "run_jobs": true
}
```

Phase 5 exit bar: **≥5 families and ≥50 agents**.

```http
POST /api/v1/city/scale/awaken
```

Phase 6: **10×10 = 100 agents** with unique personality fingerprints across districts.

```http
GET /api/v1/city/snapshot
GET /api/v1/city/scale/status
GET /api/v1/city/scale/path
```

---

## Path to 100 — bottlenecks

1. **LLM cost/latency** — keep children on cheap models; reserve strong models for parents/coordinators.  
2. **Tool fan-out** — raise `PERSOLA_CITY_WORKERS` and caps gradually; prefer enqueue over inline invoke under load.  
3. **District hot spots** — spread jobs across `build/viz/research/ops`.  
4. **Memory** — bounded queue; do not store full chat histories on work items.  
5. **External runtime** — Cyrex bulk sync when agents must leave Persola’s society layer.

**Suggested growth:** probe 50 → raise workers to 8 and global to 48 → probe 80 → raise per-family to 12 → probe 100 with `run_jobs=false` for spawn-only pressure, then enable jobs with district sharding.

---

## Cohesion score

```http
GET /api/v1/city/jobs/{job_id}/cohesion
```

`score = 0.6 * participation + 0.4 * tool_success_rate` where participation is the fraction of family members who wrote an artifact or started a run.

---

## Disk commons mirror (Phase 9)

Set `PERSOLA_CITY_COMMONS_ROOT` to a writable directory. Every `workspace_write` also lands at:

```text
$PERSOLA_CITY_COMMONS_ROOT/jobs/{job_id}/{artifact_path}
```

```http
GET /api/v1/city/commons/status
GET /api/v1/city/commons/status?job_id={uuid}
GET /api/v1/city/export/austin
```

The Austin pack is a self-contained JSON snapshot (graph, events, artifact samples) for external visualization.
