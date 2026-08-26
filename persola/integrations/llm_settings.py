"""Runtime LLM settings — file-backed, overridable by env.

Secrets may be stored in ``.persola/settings.json`` for local use, or supplied
via environment variables (env wins when the file field is empty).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.RLock()

DEFAULT_SETTINGS_PATH = Path(
    os.getenv("PERSOLA_SETTINGS_PATH")
    or Path(__file__).resolve().parents[2] / ".persola" / "settings.json"
)

CLOUD_MODEL_CATALOG: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "o4-mini"],
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
    ],
    "gemini": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-pro"],
    "openrouter": [
        "openrouter/auto",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o-mini",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.1-70b-instruct",
    ],
    "ollama": [],
}


class LLMSettings(BaseModel):
    provider: str = Field(default="ollama")
    model: str = Field(default="qwen3-coder:30b")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1, le=128_000)

    ollama_base_url: str = Field(default="http://127.0.0.1:11434")

    openai_api_key: str = ""
    openai_base_url: str = ""  # optional Azure / proxy
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/auto"

    def resolved_api_key(self, provider: str | None = None) -> str:
        p = (provider or self.provider).lower()
        file_key = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(p, "")
        if file_key.strip():
            return file_key.strip()
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        # Accept GOOGLE_API_KEY as alias for Gemini
        if p == "gemini":
            return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        return (os.getenv(env_map.get(p, ""), "") or "").strip()

    def resolved_model(self, provider: str | None = None) -> str:
        p = (provider or self.provider).lower()
        if self.model.strip():
            # Prefer explicit active model when it matches the provider context
            return self.model.strip()
        defaults = {
            "ollama": os.getenv("LOCAL_LLM_MODEL", "qwen3-coder:30b"),
            "openai": self.openai_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "anthropic": self.anthropic_model
            or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "gemini": self.gemini_model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            "openrouter": self.openrouter_model or os.getenv("OPENROUTER_MODEL", "openrouter/auto"),
        }
        return defaults.get(p, "qwen3-coder:30b")

    def public_dict(self) -> dict[str, Any]:
        """Safe for API responses — masks secrets."""

        def mask(v: str) -> str:
            v = (v or "").strip()
            if not v:
                return ""
            if len(v) <= 8:
                return "••••••••"
            return f"{v[:4]}…{v[-4:]}"

        return {
            "provider": self.provider,
            "model": self.resolved_model(),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "ollama_base_url": self.ollama_base_url
            or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "openai_base_url": self.openai_base_url or os.getenv("OPENAI_BASE_URL", ""),
            "openrouter_base_url": self.openrouter_base_url
            or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "openai_api_key_set": bool(self.resolved_api_key("openai")),
            "anthropic_api_key_set": bool(self.resolved_api_key("anthropic")),
            "gemini_api_key_set": bool(self.resolved_api_key("gemini")),
            "openrouter_api_key_set": bool(self.resolved_api_key("openrouter")),
            "openai_api_key_masked": mask(self.resolved_api_key("openai")),
            "anthropic_api_key_masked": mask(self.resolved_api_key("anthropic")),
            "gemini_api_key_masked": mask(self.resolved_api_key("gemini")),
            "openrouter_api_key_masked": mask(self.resolved_api_key("openrouter")),
            "catalog": CLOUD_MODEL_CATALOG,
            "settings_path": str(DEFAULT_SETTINGS_PATH),
        }


_cached: LLMSettings | None = None


def _env_bootstrap() -> dict[str, Any]:
    provider = (
        os.getenv("PERSOLA_LLM_PROVIDER") or os.getenv("DEFAULT_PROVIDER") or "ollama"
    ).lower()
    model = (
        os.getenv("PERSOLA_LLM_MODEL")
        or os.getenv("DEFAULT_MODEL")
        or os.getenv("LOCAL_LLM_MODEL")
        or "qwen3-coder:30b"
    )
    return {
        "provider": provider,
        "model": model,
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "gemini_api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "openrouter_base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    }


def load_llm_settings(*, force: bool = False) -> LLMSettings:
    global _cached
    with _LOCK:
        if _cached is not None and not force:
            return _cached
        data = _env_bootstrap()
        path = DEFAULT_SETTINGS_PATH
        if path.is_file():
            try:
                file_data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(file_data, dict):
                    data.update({k: v for k, v in file_data.items() if v is not None})
            except (OSError, json.JSONDecodeError):
                pass
        _cached = LLMSettings.model_validate(data)
        return _cached


def save_llm_settings(patch: dict[str, Any]) -> LLMSettings:
    global _cached
    with _LOCK:
        current = load_llm_settings(force=True).model_dump()
        # Empty string for secrets means "leave unchanged" unless explicitly cleared via null
        for key, value in patch.items():
            if key.endswith("_api_key") and value == "":
                continue
            if value is None and key.endswith("_api_key"):
                current[key] = ""
                continue
            if key in current:
                current[key] = value
        settings = LLMSettings.model_validate(current)
        path = DEFAULT_SETTINGS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        # Persist without echoing env-only empties awkwardly — store the model dump
        path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
        _cached = settings
        # Mirror critical env for child processes / existing readers
        os.environ["OLLAMA_BASE_URL"] = settings.ollama_base_url
        os.environ["DEFAULT_PROVIDER"] = settings.provider
        os.environ["DEFAULT_MODEL"] = settings.model
        os.environ["PERSOLA_LLM_PROVIDER"] = settings.provider
        os.environ["PERSOLA_LLM_MODEL"] = settings.model
        return settings
