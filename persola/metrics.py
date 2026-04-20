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


# ---------------------------------------------------------------------------
# Helper callables for route handlers
# ---------------------------------------------------------------------------

def record_llm_tokens(provider: str, model: str, tokens: int) -> None:
    """Increment the LLM token counter.  Call from invoke_agent on success."""
    if tokens and tokens > 0:
        LLM_TOKENS_TOTAL.labels(provider=provider, model=model).inc(tokens)


def set_personas_total(count: int) -> None:
    PERSONAS_TOTAL.set(count)


def set_agents_total(count: int) -> None:
    AGENTS_TOTAL.set(count)


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
