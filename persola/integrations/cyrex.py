from __future__ import annotations

from typing import Any
import os

import httpx

from ..models import PersonaProfile


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class CyrexClient:
    """HTTP client for the Cyrex service."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 20):
        self.base_url = (base_url or os.getenv("CYREX_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("CYREX_API_KEY", "")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def push_persona(self, persona: PersonaProfile) -> dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("Cyrex is not configured")

        payload = {
            "persona": persona.model_dump(mode="json"),
            "source": "persola",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/cyrex/sync/{persona.id}",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def pull_persona(self, cyrex_id: str) -> PersonaProfile:
        if not self.is_configured:
            raise RuntimeError("Cyrex is not configured")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/cyrex/import/{cyrex_id}",
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

        candidate = self._extract_persona_payload(data)
        if not isinstance(candidate, dict):
            raise ValueError("Cyrex import did not return a persona payload")

        return self._to_persona_profile(candidate, cyrex_id)

    async def list_cyrex_agents(self) -> list[dict[str, Any]]:
        if not self.is_configured:
            return []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/cyrex/agents",
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("agents", "items", "data", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return value

        return []

    async def is_available(self) -> bool:
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/cyrex/status",
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "available" in data:
                    return bool(data["available"])
                return True
        except Exception:
            return False

    def _extract_persona_payload(self, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("persona", "agent", "profile", "data"):
                value = data.get(key)
                if isinstance(value, dict):
                    return value
            return data
        return data

    def _to_persona_profile(self, payload: dict[str, Any], cyrex_id: str) -> PersonaProfile:
        defaults = PersonaProfile(name=f"Cyrex Agent {cyrex_id}").model_dump()
        knobs = payload.get("knobs") if isinstance(payload.get("knobs"), dict) else {}
        traits = payload.get("traits") if isinstance(payload.get("traits"), dict) else {}

        def pick(*keys: str, default: Any = None) -> Any:
            for key in keys:
                if key in payload and payload[key] is not None:
                    return payload[key]
            return default

        def knob(name: str) -> float:
            raw = payload.get(name)
            if raw is None:
                raw = knobs.get(name)
            if raw is None:
                raw = traits.get(name)
            return _coerce_float(raw, defaults[name])

        persona_payload = {
            "id": str(pick("id", "cyrex_id", default=cyrex_id)),
            "name": str(pick("name", "title", "agent_name", default=defaults["name"])),
            "description": str(pick("description", "bio", "summary", default=defaults["description"])),
            "model": str(pick("model", "llm_model", default=defaults["model"])),
            "temperature": _coerce_float(pick("temperature", default=defaults["temperature"]), defaults["temperature"]),
            "max_tokens": _coerce_int(pick("max_tokens", "max_output_tokens", default=defaults["max_tokens"]), defaults["max_tokens"]),
            "creativity": knob("creativity"),
            "humor": knob("humor"),
            "formality": knob("formality"),
            "verbosity": knob("verbosity"),
            "empathy": knob("empathy"),
            "confidence": knob("confidence"),
            "openness": knob("openness"),
            "conscientiousness": knob("conscientiousness"),
            "extraversion": knob("extraversion"),
            "agreeableness": knob("agreeableness"),
            "neuroticism": knob("neuroticism"),
            "reasoning_depth": knob("reasoning_depth"),
            "step_by_step": knob("step_by_step"),
            "creativity_in_reasoning": knob("creativity_in_reasoning"),
            "synthetics": knob("synthetics"),
            "abstraction": knob("abstraction"),
            "patterns": knob("patterns"),
            "accuracy": knob("accuracy"),
            "reliability": knob("reliability"),
            "caution": knob("caution"),
            "consistency": knob("consistency"),
            "self_correction": knob("self_correction"),
            "transparency": knob("transparency"),
        }
        return PersonaProfile(**persona_payload)


HAS_CYREX = bool(os.getenv("CYREX_URL") and os.getenv("CYREX_API_KEY"))


__all__ = ["CyrexClient", "HAS_CYREX"]