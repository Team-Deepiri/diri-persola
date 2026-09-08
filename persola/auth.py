import json
import os
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_EXEMPT_PREFIXES = ("/health", "/", "/ui", "/static", "/metrics", "/api/v1/city/health")


def _get_valid_keys() -> frozenset[str]:
    raw = os.environ.get("PERSOLA_API_KEYS", "")
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def _get_key_tenant_map() -> dict[str, UUID]:
    """Map an API key to a tenant id from PERSOLA_API_KEY_TENANTS.

    JSON object of ``{"<api-key>": "<tenant-uuid>"}``. Keys absent from the
    mapping are assigned the DEFAULT_TENANT sentinel (see persola.db.models).
    """
    raw = os.environ.get("PERSOLA_API_KEY_TENANTS", "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    mapping: dict[str, UUID] = {}
    for key, tenant in data.items():
        try:
            mapping[str(key).strip()] = UUID(str(tenant))
        except (ValueError, TypeError):
            continue
    return mapping


def _is_exempt(path: str) -> bool:
    if path == "/":
        return True
    for prefix in _EXEMPT_PREFIXES:
        if prefix != "/" and path.startswith(prefix):
            return True
    return False


class APIKeyAuth(BaseHTTPMiddleware):
    """
    API key middleware with tenant resolution.

    Keys stored in environment (PERSOLA_API_KEYS=key1,key2). Used via the
    X-API-Key header. Each key resolves to a tenant id (PERSOLA_API_KEY_TENANTS
    JSON mapping; DEFAULT_TENANT when unmapped), stored on `request.state` so
    handlers can scope their repositories.

    Paths /health, /, /ui, /static/* are exempt. Returns 401 on missing or
    invalid key. Auth is effectively disabled when no keys are configured.
    """

    async def dispatch(self, request: Request, call_next):
        if _is_exempt(request.url.path):
            request.state.tenant_id = None
            return await call_next(request)

        valid_keys = _get_valid_keys()

        # If no keys are configured, auth is effectively disabled.
        if not valid_keys:
            request.state.tenant_id = None
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key not in valid_keys:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        request.state.tenant_id = _get_key_tenant_map().get(provided_key)
        return await call_next(request)


def get_request_tenant_id(request: Request):
    """FastAPI dependency returning the resolved tenant id for the request.

    Resolved tenant comes from ``request.state.tenant_id`` (set by
    ``APIKeyAuth`` from the API key → tenant mapping). When it is ``None`` —
    i.e. the path was exempt from auth (``/health``, ``/ui``, ``/static``,
    ``/metrics``, ``/api/v1/city/health``) or no API keys are configured —
    it falls back to ``DEFAULT_TENANT`` so those endpoints retain the system
    tenant behaviour.

    SECURITY NOTE: this means exempt and unauthenticated requests operate under
    the ``DEFAULT_TENANT`` (sentinel) context. That sentinel must only ever own
    data intended to be globally/system accessible (e.g. pre-seeded presets and
    the default org chart). Any endpoint that reads or writes user-scoped data
    MUST NOT leak into ``DEFAULT_TENANT``; such endpoints should require an
    authenticated key that maps to a real tenant. Keep ``DEFAULT_TENANT`` data
    strictly system-managed and non-trusting of request-supplied content.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        from .db.models import DEFAULT_TENANT

        tenant_id = DEFAULT_TENANT
    return tenant_id
