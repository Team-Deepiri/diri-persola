"""
LLM Integration for Persola.

Providers: ollama (local), openai, anthropic, gemini, openrouter.
Active selection comes from ``llm_settings`` (UI / .persola/settings.json / env).
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from typing import Any, Protocol, runtime_checkable

import httpx
import structlog

from .llm_settings import load_llm_settings

log = structlog.get_logger("persola.llm")


@runtime_checkable
class LLMProvider(Protocol):
    """Formal interface that every LLM client must satisfy."""

    def is_available(self) -> bool: ...

    async def generate(self, prompt: str) -> str: ...

    async def chat(self, messages: list[dict], system_prompt: str = "") -> str: ...

    async def generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]: ...

    def supports_tool_calling(self) -> bool: ...


class OllamaClient:
    """Ollama HTTP client (local or remote)."""

    def __init__(
        self,
        model: str = "qwen3-coder:30b",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: int = 300,
    ):
        settings = load_llm_settings()
        self.model = model
        self.base_url = (
            base_url
            or settings.ollama_base_url
            or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models") or []
            return [
                m.get("name") or m.get("model") for m in models if m.get("name") or m.get("model")
            ]

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")

    async def generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]:
        async with (
            httpx.AsyncClient(timeout=self.timeout) as client,
            client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                    "stream": True,
                },
            ) as response,
        ):
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    j = json.loads(line)
                    if "response" in j:
                        yield j["response"]
                except (ValueError, TypeError) as exc:
                    log.debug("ollama.stream.skip", error=str(exc))

    async def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        formatted: list[dict] = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": formatted,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")

    def supports_tool_calling(self) -> bool:
        return True


class OpenAICompatibleClient:
    """OpenAI SDK wrapper — also used for OpenRouter / custom base URLs."""

    def __init__(
        self,
        *,
        provider_label: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        self.provider_label = provider_label
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/") or None
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    async def generate(self, prompt: str) -> str:
        return await self.chat([{"role": "user", "content": prompt}])

    async def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        formatted: list[dict] = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""

    def supports_tool_calling(self) -> bool:
        return True


class AnthropicClientWrapper:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def generate(self, prompt: str) -> str:
        return await self.chat([{"role": "user", "content": prompt}])

    async def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        client = self._get_client()
        kwargs: dict[str, Any] = {}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=messages,
            **kwargs,
        )
        return response.content[0].text

    def supports_tool_calling(self) -> bool:
        return True


class GeminiClient:
    """Google Gemini generateContent via REST (no heavy SDK required)."""

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str) -> str:
        return await self.chat([{"role": "user", "content": prompt}])

    async def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") != "assistant" else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, params={"key": self.api_key}, json=body)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return ""
            parts = (candidates[0].get("content") or {}).get("parts") or []
            return "".join(p.get("text", "") for p in parts)

    def supports_tool_calling(self) -> bool:
        return True


# Back-compat alias
OpenAIClientWrapper = OpenAICompatibleClient


class PersolaLLM:
    """Unified LLM interface. Provider comes from settings unless overridden."""

    def __init__(
        self,
        provider: str = "auto",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        settings = load_llm_settings()
        self.kwargs = kwargs
        self._provider: LLMProvider | None = None
        self._provider_type: str | None = None

        if provider == "auto":
            provider = settings.provider or "ollama"

        self._provider_type = provider.lower()
        self.model = model or settings.resolved_model(self._provider_type)
        self.temperature = temperature if temperature is not None else settings.temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.max_tokens
        self._initialize_provider(self._provider_type)

    def _initialize_provider(self, provider: str) -> None:
        settings = load_llm_settings()

        if provider == "openai":
            self._provider = OpenAICompatibleClient(
                provider_label="openai",
                model=self.model,
                api_key=settings.resolved_api_key("openai"),
                base_url=settings.openai_base_url or None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif provider == "openrouter":
            self._provider = OpenAICompatibleClient(
                provider_label="openrouter",
                model=self.model,
                api_key=settings.resolved_api_key("openrouter"),
                base_url=settings.openrouter_base_url or "https://openrouter.ai/api/v1",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif provider == "anthropic":
            self._provider = AnthropicClientWrapper(
                model=self.model,
                api_key=settings.resolved_api_key("anthropic"),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif provider == "gemini":
            self._provider = GeminiClient(
                model=self.model,
                api_key=settings.resolved_api_key("gemini"),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif provider == "ollama":
            self._provider = OllamaClient(
                model=self.model,
                base_url=settings.ollama_base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        else:
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                "Use ollama, openai, anthropic, gemini, or openrouter."
            )

        log.info("llm.init", provider=provider, model=self.model)

    def get_provider_type(self) -> str:
        return self._provider_type or "unknown"

    def is_available(self) -> bool:
        if self._provider is None:
            return False
        return self._provider.is_available()

    async def generate(self, prompt: str) -> str:
        if self._provider is None:
            raise RuntimeError("No provider initialized")
        return await self._provider.generate(prompt)

    async def generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]:
        if hasattr(self._provider, "generate_streaming"):
            async for chunk in self._provider.generate_streaming(prompt):
                yield chunk
        else:
            result = await self.generate(prompt)
            yield result

    async def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        if self._provider is None:
            raise RuntimeError("No provider initialized")
        if hasattr(self._provider, "chat"):
            return await self._provider.chat(messages, system_prompt=system_prompt)
        parts: list[str] = []
        if system_prompt:
            parts.append(f"System: {system_prompt}\n")
        for msg in messages:
            role = msg.get("role", "user").capitalize()
            parts.append(f"{role}: {msg.get('content', '')}")
        parts.append("Assistant:")
        return await self._provider.generate("\n".join(parts))

    def get_config(self) -> dict[str, Any]:
        return {
            "provider": self._provider_type,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "available": self.is_available(),
        }


def get_llm_provider(
    provider: str = "auto",
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> PersolaLLM:
    """Factory — respects saved settings when provider/model are auto/None."""
    return PersolaLLM(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


HAS_CYREX = bool(os.getenv("CYREX_URL") and os.getenv("CYREX_API_KEY"))

__all__ = [
    "HAS_CYREX",
    "AnthropicClientWrapper",
    "GeminiClient",
    "LLMProvider",
    "OllamaClient",
    "OpenAIClientWrapper",
    "OpenAICompatibleClient",
    "PersolaLLM",
    "get_llm_provider",
]
