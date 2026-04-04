import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


_EXEMPT_PREFIXES = ("/health", "/", "/ui", "/static")


def _get_valid_keys() -> frozenset[str]:
    raw = os.environ.get("PERSOLA_API_KEYS", "")
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def _is_exempt(path: str) -> bool:
    if path == "/":
        return True
    for prefix in _EXEMPT_PREFIXES:
        if prefix != "/" and path.startswith(prefix):
            return True
    return False


class APIKeyAuth(BaseHTTPMiddleware):
    """
    Simple API key middleware.
    Keys stored in environment (PERSOLA_API_KEYS=key1,key2).
    Used via X-API-Key header.
    Paths /health, /, /ui, /static/* are exempt.
    Returns 401 on missing or invalid key.
    """

    async def dispatch(self, request: Request, call_next):
        if _is_exempt(request.url.path):
            return await call_next(request)

        valid_keys = _get_valid_keys()

        # If no keys are configured, auth is effectively disabled.
        if not valid_keys:
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key not in valid_keys:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
