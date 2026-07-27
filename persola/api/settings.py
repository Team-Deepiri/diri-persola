"""LLM / runtime settings API."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..integrations.llm import OllamaClient, get_llm_provider
from ..integrations.llm_settings import (
	CLOUD_MODEL_CATALOG,
	load_llm_settings,
	save_llm_settings,
)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class LLMSettingsPatch(BaseModel):
	provider: Optional[str] = None
	model: Optional[str] = None
	temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
	max_tokens: Optional[int] = Field(default=None, ge=1, le=128_000)
	ollama_base_url: Optional[str] = None
	openai_base_url: Optional[str] = None
	openrouter_base_url: Optional[str] = None
	openai_api_key: Optional[str] = None
	anthropic_api_key: Optional[str] = None
	gemini_api_key: Optional[str] = None
	openrouter_api_key: Optional[str] = None
	openai_model: Optional[str] = None
	anthropic_model: Optional[str] = None
	gemini_model: Optional[str] = None
	openrouter_model: Optional[str] = None


class LLMTestRequest(BaseModel):
	prompt: str = Field(default="Reply with exactly: ok", max_length=500)


@router.get("/llm")
async def get_llm_settings() -> dict[str, Any]:
	settings = load_llm_settings()
	return settings.public_dict()


@router.patch("/llm")
async def patch_llm_settings(body: LLMSettingsPatch) -> dict[str, Any]:
	patch = body.model_dump(exclude_unset=True)
	provider = (patch.get("provider") or load_llm_settings().provider or "").lower()
	if "provider" in patch:
		provider = str(patch["provider"]).lower()
		allowed = {"ollama", "openai", "anthropic", "gemini", "openrouter"}
		if provider not in allowed:
			raise HTTPException(
				status_code=400,
				detail=f"provider must be one of {sorted(allowed)}",
			)
		patch["provider"] = provider
	settings = save_llm_settings(patch)
	return {"ok": True, **settings.public_dict()}


@router.get("/llm/models")
async def list_llm_models(provider: Optional[str] = None) -> dict[str, Any]:
	settings = load_llm_settings()
	p = (provider or settings.provider or "ollama").lower()
	if p == "ollama":
		client = OllamaClient(base_url=settings.ollama_base_url)
		try:
			models = await client.list_models()
			return {
				"provider": "ollama",
				"base_url": client.base_url,
				"available": True,
				"models": models,
			}
		except Exception as _exc:
			return {
				"provider": "ollama",
				"base_url": client.base_url,
				"available": False,
				"models": [],
				"error": "Unable to fetch Ollama models.",
			}
	return {
		"provider": p,
		"available": bool(settings.resolved_api_key(p)),
		"models": CLOUD_MODEL_CATALOG.get(p, []),
	}


@router.post("/llm/test")
async def test_llm(body: LLMTestRequest) -> dict[str, Any]:
	settings = load_llm_settings()
	llm = get_llm_provider(
		provider=settings.provider,
		model=settings.resolved_model(),
		temperature=settings.temperature,
		max_tokens=min(settings.max_tokens, 128),
	)
	if not llm.is_available():
		raise HTTPException(
			status_code=503,
			detail=(
				f"Provider '{settings.provider}' is not available. "
				"Check Ollama is running or set the provider API key in Settings."
			),
		)
	try:
		text = await llm.generate(body.prompt)
	except Exception as exc:
		raise HTTPException(status_code=502, detail=str(exc)) from exc
	return {
		"ok": True,
		"provider": llm.get_provider_type(),
		"model": llm.model,
		"response": text[:2000],
	}


@router.get("/llm/ollama/health")
async def ollama_health() -> dict[str, Any]:
	settings = load_llm_settings()
	base = settings.ollama_base_url.rstrip("/")
	try:
		async with httpx.AsyncClient(timeout=5.0) as client:
			resp = await client.get(f"{base}/api/tags")
			resp.raise_for_status()
			models = [m.get("name") for m in (resp.json().get("models") or [])]
			return {"ok": True, "base_url": base, "models": models, "count": len(models)}
	except Exception:
		return {
			"ok": False,
			"base_url": base,
			"error": "Unable to reach Ollama service.",
			"models": [],
		}
