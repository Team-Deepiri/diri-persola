"""
Phase 6 – Auth, Rate Limiting & Security validation checklist.

Checklist:
  [6.1] Requests without X-API-Key return 401 (when auth enabled)
  [6.1] /health responds without auth header (exempt)
  [6.2] 31st invoke request in a minute returns 429
  [6.3] Persona name >200 chars returns 422
  [6.3] Knob value 1.1 returns 422

The auth and rate-limit tests use minimal stub apps (no database required).
The validation tests are pure Pydantic unit tests.
"""

import os
import uuid
from contextlib import contextmanager

import pytest
from fastapi import FastAPI, Request
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def env_api_keys(keys: str | None):
    """Temporarily set (or unset) PERSOLA_API_KEYS for the duration of the block."""
    old = os.environ.get("PERSOLA_API_KEYS")
    if keys is not None:
        os.environ["PERSOLA_API_KEYS"] = keys
    else:
        os.environ.pop("PERSOLA_API_KEYS", None)
    try:
        yield
    finally:
        if old is not None:
            os.environ["PERSOLA_API_KEYS"] = old
        else:
            os.environ.pop("PERSOLA_API_KEYS", None)


def _make_stub_app(api_keys: str | None) -> Starlette:
    """
    Minimal Starlette app wired with APIKeyAuth.
    Routes mirror the paths relevant to the auth checklist.
    """
    from persola.auth import APIKeyAuth

    async def root(request: StarletteRequest):
        return JSONResponse({"ok": True})

    async def health(request: StarletteRequest):
        return JSONResponse({"status": "healthy"})

    async def protected(request: StarletteRequest):
        return JSONResponse({"data": "secret"})

    routes = [
        Route("/", root),
        Route("/health", health),
        Route("/api/v1/personas", protected),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(APIKeyAuth)
    return app


# ---------------------------------------------------------------------------
# 6.1  Auth – X-API-Key header
# ---------------------------------------------------------------------------

def test_missing_key_returns_401():
    """[6.1] No X-API-Key header → 401."""
    with env_api_keys("valid-key-abc"):
        client = TestClient(_make_stub_app("valid-key-abc"), raise_server_exceptions=False)
        r = client.get("/api/v1/personas")
    assert r.status_code == 401


def test_invalid_key_returns_401():
    """[6.1] Wrong X-API-Key value → 401."""
    with env_api_keys("valid-key-abc"):
        client = TestClient(_make_stub_app("valid-key-abc"), raise_server_exceptions=False)
        r = client.get("/api/v1/personas", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


def test_valid_key_accepted():
    """[6.1] Correct X-API-Key → request passes through (200)."""
    with env_api_keys("valid-key-abc"):
        client = TestClient(_make_stub_app("valid-key-abc"), raise_server_exceptions=False)
        r = client.get("/api/v1/personas", headers={"X-API-Key": "valid-key-abc"})
    assert r.status_code == 200


def test_auth_disabled_when_no_keys_configured():
    """[6.1] Empty PERSOLA_API_KEYS → auth bypass (safe for local dev)."""
    with env_api_keys(None):
        client = TestClient(_make_stub_app(None), raise_server_exceptions=False)
        r = client.get("/api/v1/personas")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 6.1  Auth – /health is exempt
# ---------------------------------------------------------------------------

def test_health_exempt_no_key():
    """[6.1] GET /health without X-API-Key must not return 401."""
    with env_api_keys("valid-key-abc"):
        client = TestClient(_make_stub_app("valid-key-abc"), raise_server_exceptions=False)
        r = client.get("/health")
    assert r.status_code == 200


def test_health_exempt_wrong_key():
    """[6.1] GET /health with wrong key still passes (exempt path)."""
    with env_api_keys("valid-key-abc"):
        client = TestClient(_make_stub_app("valid-key-abc"), raise_server_exceptions=False)
        r = client.get("/health", headers={"X-API-Key": "garbage"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 6.2  Rate limiting – 31st invoke request returns 429
# ---------------------------------------------------------------------------

def test_invoke_31st_request_returns_429():
    """[6.2] Rate limit 30/minute on invoke: the 31st request must return 429."""
    test_limiter = Limiter(key_func=get_remote_address)
    agent_id = str(uuid.uuid4())

    rate_app = FastAPI()
    rate_app.state.limiter = test_limiter
    rate_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @rate_app.post("/api/v1/agents/{agent_id}/invoke")
    @test_limiter.limit("30/minute")
    async def stub_invoke(request: Request, agent_id: str):
        return {"ok": True}

    client = TestClient(rate_app, raise_server_exceptions=False)
    statuses = [
        client.post(f"/api/v1/agents/{agent_id}/invoke").status_code
        for _ in range(31)
    ]

    assert all(s == 200 for s in statuses[:30]), (
        f"Requests 1–30 should succeed; got {statuses[:30]}"
    )
    assert statuses[30] == 429, (
        f"Request 31 should be rate-limited (429); got {statuses[30]}"
    )


# ---------------------------------------------------------------------------
# 6.3  Input validation – Pydantic unit tests
# ---------------------------------------------------------------------------

def test_persona_name_over_200_chars_rejected():
    """[6.3] PersonaProfile.name > 200 chars → ValidationError (→ 422 via API)."""
    from persola.models import PersonaProfile

    with pytest.raises(ValidationError):
        PersonaProfile(name="a" * 201)


def test_persona_name_at_200_chars_accepted():
    """[6.3] PersonaProfile.name == 200 chars → valid."""
    from persola.models import PersonaProfile

    p = PersonaProfile(name="a" * 200)
    assert len(p.name) == 200


def test_knob_value_1_1_rejected():
    """[6.3] Knob field value 1.1 exceeds le=1.0 → ValidationError (→ 422 via API)."""
    from persola.models import PersonaProfile

    with pytest.raises(ValidationError):
        PersonaProfile(creativity=1.1)


def test_knob_value_exactly_1_0_accepted():
    """[6.3] Knob field value 1.0 is at boundary → valid."""
    from persola.models import PersonaProfile

    p = PersonaProfile(creativity=1.0)
    assert p.creativity == 1.0


def test_knob_value_negative_rejected():
    """[6.3] Knob field value below ge=0.0 → ValidationError."""
    from persola.models import PersonaProfile

    with pytest.raises(ValidationError):
        PersonaProfile(formality=-0.1)


def test_message_too_long_rejected():
    """[6.3] InvokeRequest.message > 32,768 chars → ValidationError (→ 422 via API)."""
    from persola.api.main import InvokeRequest

    with pytest.raises(ValidationError):
        InvokeRequest(message="x" * 32_769)


def test_message_at_limit_accepted():
    """[6.3] InvokeRequest.message == 32,768 chars → valid."""
    from persola.api.main import InvokeRequest

    req = InvokeRequest(message="x" * 32_768)
    assert len(req.message) == 32_768


def test_analysis_text_too_long_rejected():
    """[6.3] AnalysisExtractRequest.text > 50,000 chars → ValidationError (→ 422 via API)."""
    from persola.api.main import AnalysisExtractRequest

    with pytest.raises(ValidationError):
        AnalysisExtractRequest(text="x" * 50_001)


def test_analysis_text_at_limit_accepted():
    """[6.3] AnalysisExtractRequest.text == 50,000 chars → valid."""
    from persola.api.main import AnalysisExtractRequest

    req = AnalysisExtractRequest(text="x" * 50_000)
    assert len(req.text) == 50_000
