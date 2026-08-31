"""
Prometheus metrics for Persola.

Defines all metric objects and a Starlette middleware that automatically tracks
request counts and latency.  LLM token usage and entity-gauge helpers are
exposed as plain functions so individual route handlers can call them without
importing prometheus_client directly.

Metric catalogue
----------------
persola_requests_total{method, endpoint, status}
    Counter – every HTTP request (after response).

persola_request_duration_seconds{endpoint}
    Histogram – wall-clock latency per named endpoint.

persola_llm_tokens_total{provider, model}
    Counter – token usage reported by LLM providers.

persola_personas_total
    Gauge – current number of personas in the database.

persola_agents_total
    Gauge – current number of agents in the database.
"""

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

REQUESTS_TOTAL = Counter(
    "persola_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "persola_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

LLM_TOKENS_TOTAL = Counter(
    "persola_llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model"],
)

PERSONAS_TOTAL = Gauge(
    "persola_personas_total",
    "Current number of personas in the database",
)

AGENTS_TOTAL = Gauge(
    "persola_agents_total",
    "Current number of agents in the database",
)

CITY_JOBS_TOTAL = Counter(
    "persola_city_jobs_total",
    "City jobs by district and status",
    ["district", "status"],
)

CITY_TOOL_RUNS_TOTAL = Counter(
    "persola_city_tool_runs_total",
    "City commons tool invocations",
    ["tool", "status"],
)

CITY_JOB_DURATION = Histogram(
    "persola_city_job_duration_seconds",
    "City job / tool-batch wall time",
    ["district"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0, 60.0),
)

CITY_COHESION_SCORE = Gauge(
    "persola_city_cohesion_score",
    "Latest computed cohesion score (0-1) for a sampled job",
)

CITY_QUEUE_DEPTH = Gauge(
    "persola_city_queue_depth",
    "City worker queue depth",
)

CITY_ACTIVE_AGENTS = Gauge(
    "persola_city_active_agents",
    "Agents belonging to active city families (approx)",
)

CITY_LIVING_AGENTS = Gauge(
    "persola_city_living_agents",
    "Living (active) city family members",
)

CITY_DECEASED_AGENTS = Gauge(
    "persola_city_deceased_agents",
    "Deceased city family members retained for lineage",
)

CITY_GENERATION_MAX = Gauge(
    "persola_city_generation_max",
    "Highest generation index observed in the city",
)

CITY_EFFICIENCY = Gauge(
    "persola_city_efficiency",
    "Avg completed jobs per living member across families",
)

CITY_DEATHS_TOTAL = Counter(
    "persola_city_deaths_total",
    "City member deaths (natural age-out)",
)

CITY_SUCCESSIONS_TOTAL = Counter(
    "persola_city_successions_total",
    "Legacy handoffs to next-generation heirs",
)

WORKQUEUE_TASKS_TOTAL = Counter(
    "persola_workqueue_tasks_total",
    "Workqueue tasks processed by the daemon, by outcome",
    ["status"],
)

WORKQUEUE_TASK_DURATION = Histogram(
    "persola_workqueue_task_duration_seconds",
    "Workqueue task processing time (claim -> done/failed)",
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)


def record_llm_tokens(provider: str, model: str, tokens: int) -> None:
    """Increment the LLM token counter.  Call from invoke_agent on success."""
    if tokens and tokens > 0:
        LLM_TOKENS_TOTAL.labels(provider=provider, model=model).inc(tokens)


def set_personas_total(count: int) -> None:
    PERSONAS_TOTAL.set(count)


def set_agents_total(count: int) -> None:
    AGENTS_TOTAL.set(count)


def record_city_job(district: str, status: str) -> None:
    CITY_JOBS_TOTAL.labels(district=district or "build", status=status).inc()


def record_city_tool_run(tool: str, status: str) -> None:
    CITY_TOOL_RUNS_TOTAL.labels(tool=tool or "unknown", status=status).inc()


def observe_city_job_duration(district: str, seconds: float) -> None:
    CITY_JOB_DURATION.labels(district=district or "build").observe(max(0.0, seconds))


def set_city_cohesion_score(score: float) -> None:
    CITY_COHESION_SCORE.set(max(0.0, min(1.0, score)))


def set_city_queue_depth(depth: int) -> None:
    CITY_QUEUE_DEPTH.set(max(0, depth))


def set_city_active_agents(count: int) -> None:
    CITY_ACTIVE_AGENTS.set(max(0, count))


def set_city_life_vitals(
    *,
    living: int,
    deceased: int,
    generation_max: int,
    efficiency: float,
) -> None:
    CITY_LIVING_AGENTS.set(max(0, living))
    CITY_DECEASED_AGENTS.set(max(0, deceased))
    CITY_GENERATION_MAX.set(max(0, generation_max))
    CITY_EFFICIENCY.set(max(0.0, efficiency))
    CITY_ACTIVE_AGENTS.set(max(0, living))


def record_city_death(count: int = 1) -> None:
    if count > 0:
        CITY_DEATHS_TOTAL.inc(count)


def record_city_succession(count: int = 1) -> None:
    if count > 0:
        CITY_SUCCESSIONS_TOTAL.inc(count)


def record_workqueue_task(status: str) -> None:
    WORKQUEUE_TASKS_TOTAL.labels(status=status or "unknown").inc()


def observe_workqueue_task_duration(seconds: float) -> None:
    WORKQUEUE_TASK_DURATION.observe(max(0.0, seconds))


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

def _normalise_endpoint(path: str) -> str:
    """
    Replace path parameters with placeholders so high-cardinality IDs do not
    create unbounded label sets.

    e.g. /api/v1/personas/abc123 → /api/v1/personas/{id}
    """
    import re

    # UUID-shaped segments
    path = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "/{id}",
        path,
        flags=re.IGNORECASE,
    )
    # Timestamp-based persona IDs like persona_abc12345
    path = re.sub(r"/persona_[0-9a-z]+", "/{id}", path)
    # Timestamp-based agent IDs like agent_abc12345
    path = re.sub(r"/agent_[0-9a-z]+", "/{id}", path)
    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Tracks request counts and latency for every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        endpoint = _normalise_endpoint(request.url.path)
        method = request.method
        status = str(response.status_code)

        REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)

        return response


# ---------------------------------------------------------------------------
# /metrics endpoint handler
# ---------------------------------------------------------------------------

async def metrics_endpoint(request: Request) -> Response:
    """Return Prometheus text exposition format."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
