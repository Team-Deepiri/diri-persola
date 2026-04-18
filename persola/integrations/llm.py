"""
LLM Integration for Persola
Uses Ollama by default, falls back to OpenAI/Anthropic if API keys are provided
"""
from typing import Optional, Dict, Any, AsyncGenerator
import os
import structlog
import httpx

log = structlog.get_logger("persola.llm")


class OllamaClient:
    """Simple Ollama client using httpx"""
    
    def __init__(
        self,
        model: str = "llama3:8b",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: int = 300,
    ):
        self.model = model
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    async def generate(self, prompt: str) -> str:
        """Generate text from prompt"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": False,
                }
            )
            response.raise_for_status()
            return response.json().get("response", "")
    
    async def generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]:
        """Generate text with streaming"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": True,
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = line.strip()
                            if '"response"' in data:
                                import json
                                j = json.loads(data)
                                if "response" in j:
                                    yield j["response"]
                        except (ValueError, TypeError):
                            pass


class OpenAIClientWrapper:
    """Wrapper around OpenAI SDK"""
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None
    
    def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))
    
    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client
    
    async def generate(self, prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content


class AnthropicClientWrapper:
    """Wrapper around Anthropic SDK"""
    
    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None
    
    def is_available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    
    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client
    
    async def generate(self, prompt: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text


class PersolaLLM:
    """
    Unified LLM interface for Persola
    Automatically selects provider based on available API keys and settings
    Priority: OpenAI > Anthropic > Ollama
    """
    
    def __init__(
        self,
        provider: str = "auto",
        model: str = "llama3:8b",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs
        self._provider = None
        self._provider_type = None
        
        self._initialize_provider(provider)
    
    def _initialize_provider(self, provider: str):
        """Initialize the appropriate LLM provider"""
        
        if provider == "auto":
            if os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            elif os.getenv("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            else:
                provider = "ollama"
        
        self._provider_type = provider
        
        if provider == "openai":
            self._provider = OpenAIClientWrapper(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            log.info("llm.init", provider="openai", model=self.model)
            
        elif provider == "anthropic":
            self._provider = AnthropicClientWrapper(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            log.info("llm.init", provider="anthropic", model=self.model)
            
        elif provider == "ollama":
            self._provider = OllamaClient(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            log.info("llm.init", provider="ollama", model=self.model)
    
    def get_provider_type(self) -> str:
        return self._provider_type or "unknown"
    
    def is_available(self) -> bool:
        """Check if the provider is available"""
        if self._provider is None:
            return False
        return self._provider.is_available()
    
    async def generate(self, prompt: str) -> str:
        """Generate text from prompt"""
        if self._provider is None:
            raise RuntimeError("No provider initialized")
        return await self._provider.generate(prompt)
    
    async def generate_streaming(self, prompt: str) -> AsyncGenerator[str, None]:
        """Generate text with streaming"""
        if hasattr(self._provider, 'generate_streaming'):
            async for chunk in self._provider.generate_streaming(prompt):
                yield chunk
        else:
            result = await self.generate(prompt)
            yield result
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "provider": self._provider_type,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "available": self.is_available(),
        }


def get_llm_provider(
    provider: str = "auto",
    model: str = "llama3:8b",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> PersolaLLM:
    """Factory function to get LLM provider"""
    return PersolaLLM(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


HAS_CYREX = bool(os.getenv("CYREX_URL") and os.getenv("CYREX_API_KEY"))

__all__ = [
    "PersolaLLM",
    "get_llm_provider",
    "HAS_CYREX",
    "OllamaClient",
    "OpenAIClientWrapper", 
    "AnthropicClientWrapper",
]
