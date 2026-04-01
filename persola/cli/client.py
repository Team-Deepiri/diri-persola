from __future__ import annotations

from typing import Any

import click
import httpx


class CLIError(click.ClickException):
    pass


class APIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            raise CLIError(f"{exc.request.method} {exc.request.url} failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise CLIError(f"Request failed: {exc}") from exc

        if not response.content:
            return None
        return response.json()

    def api_request(self, method: str, path: str, **kwargs: Any) -> Any:
        api_path = path if path.startswith("/api/v1/") else f"/api/v1{path}"
        return self.request(method, api_path, **kwargs)