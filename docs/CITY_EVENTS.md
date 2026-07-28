# City Events Contract (Austin)

**Status:** Frozen for Phase 4  
**Transport:** `GET /api/v1/city/events` (poll) and `GET /api/v1/city/events/stream` (SSE)  
**Related:** [COMMUNAL_CITY_DESIGN.md](./COMMUNAL_CITY_DESIGN.md) §12

External visualizations (Austin) and the Persola City UI consume the same event shapes.

---

## Endpoints

Pass ``types=member.died,legacy.passed,life.aged`` and/or ``city_wide=true`` to follow generational events across the city without a family id.

### Poll (≤2s recommended)

```http
GET /api/v1/city/events?family_id={uuid}&after={event_id}&limit=100
GET /api/v1/city/events?job_id={uuid}&since={iso8601}
```

Response:

```json
{
  "events": [ /* CityEvent objects */ ],
  "count": 3
}
```

### Server-Sent Events

```http
GET /api/v1/city/events/stream?family_id={uuid}&after={event_id}&poll_seconds=1
GET /api/v1/city/events/stream?city_wide=true&types=member.died,legacy.passed,life.aged&poll_seconds=1
```

- Content-Type: `text/event-stream`
- Named event: `city`
- Data: single JSON object per message (same shape as poll items)
- Keepalive comments: `: keepalive`
- First message may be `stream.hello` (non-persisted control event; includes `city_wide` / `types` when set)
- Optional `max_cycles` ends the stream with `stream.done` (useful for tests / finite clients)
- `city_wide=true` streams across families (no `family_id` required)
- `types=` comma-separated event type filter (Phase 12)

Example client:

```js
const es = new EventSource(`/api/v1/city/events/stream?family_id=${familyId}`);
es.addEventListener('city', (ev) => {
  const event = JSON.parse(ev.data);
  // render pulse / update graph
});
```

---

## CityEvent object

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (uuid) | Stable id; use as `after` cursor. Absent on control events. |
| `family_id` | string \| null | Family scope |
| `job_id` | string \| null | Job scope when applicable |
| `event_type` | string | See catalog below |
| `payload` | object | Type-specific fields |
| `created_at` | string (ISO-8601) \| null | Server timestamp |

---

## Event type catalog

### `agent.spawned`

Emitted when a family member (parent or child) is created.

```json
{
  "event_type": "agent.spawned",
  "payload": {
    "family_id": "...",
    "member_id": "...",
    "agent_id": "...",
    "parent_id": null,
    "role": "parent",
    "role_label": "coordinator"
  }
}
```

Child spawn includes `parent_id`, `parent_agent_id`, `knob_overrides`, `tool_tags`.

### `artifact.written`

```json
{
  "event_type": "artifact.written",
  "payload": {
    "artifact_id": "...",
    "path": "hello.py",
    "version": 1,
    "size_bytes": 42,
    "agent_id": "...",
    "job_id": "..."
  }
}
```

### `run.started` / `run.finished`

```json
{
  "event_type": "run.finished",
  "payload": {
    "run_id": "...",
    "tool": "run_python",
    "status": "succeeded",
    "duration_ms": 12,
    "agent_id": "...",
    "job_id": "..."
  }
}
```

`status` values: `pending`, `running`, `succeeded`, `failed`, `timeout`, `denied`.

### `job.started` / `job.completed`

```json
{
  "event_type": "job.started",
  "payload": {
    "job_id": "...",
    "family_id": "...",
    "goal": "...",
    "district": "build",
    "status": "pending"
  }
}
```

### `cohesion.merge`

```json
{
  "event_type": "cohesion.merge",
  "payload": {
    "summary": "...",
    "roles": ["coordinator", "analyst", "executor"],
    "parent_id": "...",
    "parent_agent_id": "...",
    "child_ids": ["...", "..."],
    "score": 0.72,
    "threshold": 0.35
  }
}
```

### `cohesion.veto`

Parent rejected the merge (Phase 7). Same identity fields as merge; job ends `failed`.

### `city.pulse.started` / `city.pulse.finished`

City-wide pulse wave (Phase 7). Payload includes `district`, `family_id`, `agent_id`, and on finish `cohesion` + `decision`.

### `city.conduct.started` / `city.conduct.finished`

City conductor wave (Phase 10). Payload includes `mode` (`llm`|`tools`), `district`, `ok`, `cohesion`, `decision`.

### `life.aged`

Member aged one or more ticks. Payload: `member_id`, `age_ticks`, `max_age_ticks`, `generation`, `growth`, `structured_thinking`.

### `member.died`

Natural end of an agent’s active life. Payload: `member_id`, `generation`, `goals`, `dreams`. Graph: mark node deceased (ghost).

### `legacy.passed`

Knowledge/personality handoff to the next generation. Payload: `from_member_id`, `to_member_id`, `generation`, `goals`, `tool_tags`.

### `cyrex.sync.finished`

Bulk Cyrex push for a family finished. Payload: `synced`, `failed`, `skipped`, `living_only`.

### `viz.pulse` / `viz.custom`

Optional viz-only pulses from `emit_viz_event` (allowlisted).

### Control (stream only, not persisted)

| Type | Purpose |
|------|---------|
| `stream.hello` | Stream connected |
| `stream.error` | Recoverable stream-side error |
| `stream.done` | Finite stream finished (`max_cycles`) |

---

## Graph mapping hints

| Event | Suggested viz action |
|-------|----------------------|
| `agent.spawned` | Add/highlight node; draw edge from `parent_id` |
| `artifact.written` | Pulse node `agent_id`; show path chip |
| `run.started` | Soft pulse on `agent_id` |
| `run.finished` | Strong pulse; color by status |
| `job.started` | Banner / district tint |
| `job.completed` | Settle pulses; show summary |
| `cohesion.merge` | Flash edges / parent node |
| `cohesion.veto` | Dim parent / red pulse |
| `city.pulse.started` | District wash brightens |
| `city.pulse.finished` | Settle; show cohesion chip |
| `life.aged` | Age ring / growth tick on node |
| `member.died` | Ghost node; keep lineage edge |
| `legacy.passed` | Spawn heir; flash legacy edge from deceased → heir |

---

## Compatibility

- Additive `payload` fields are allowed without version bump.
- Renaming or removing catalog `event_type` values requires a new `payload_version` field (future).
- Persola City UI and Austin should treat unknown `event_type` values as no-ops (forward compatible).
