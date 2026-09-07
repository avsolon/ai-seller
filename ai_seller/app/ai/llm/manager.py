"""LLM Manager - manages LLM providers and generation."""

import re
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LLMMessage:
    """A single message in a chat-style LLM request (doc 10)."""

    role: str
    content: str


@dataclass
class LLMResponse:
    """Response from LLM."""
    text: str
    provider: str
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    metadata: Dict[str, Any]


_RETRYABLE_HINTS = (
    "timed out",
    "timeout",
    "temporarily unavailable",
    "unavailable",
    "service unavailable",
    "network",
    "connection refused",
    "connect error",
    "rate limit",
    "too many requests",
)


def _is_retryable(exc: Exception) -> bool:
    """Selective fallback policy: only infra errors trigger a fallback (doc 10).

    Prompt/schema errors are deliberately NOT retried.
    """
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    try:
        import httpx
    except Exception:  # pragma: no cover - depends on optional driver
        httpx = None  # type: ignore

    if httpx is not None:
        if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500 or exc.response.status_code == 429

    msg = str(exc).lower()
    if any(hint in msg for hint in _RETRYABLE_HINTS):
        return True
    if re.search(r"\b(5\d\d|429)\b", msg):
        return True
    return False


class LLMProvider:
    """Base LLM Provider interface."""

    def __init__(self, name: str):
        """Initialize provider."""
        self.name = name

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using the LLM."""
        raise NotImplementedError("generate method must be implemented")

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using chat interface."""
        raise NotImplementedError("chat method must be implemented")


class OllamaProvider(LLMProvider):
    """Ollama LLM Provider."""

    def __init__(self):
        """Initialize Ollama provider."""
        super().__init__("ollama")
        self.base_url = settings.ollama_base_url
        self.default_model = settings.ollama_default_model

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using Ollama."""
        import httpx
        import time
        
        model = model or self.default_model
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False,
                        **kwargs,
                    },
                )
                
                if response.status_code != 200:
                    raise Exception(f"Ollama error: {response.status_code} - {response.text}")
                
                data = response.json()
                
                latency_ms = (time.time() - start_time) * 1000
                
                return LLMResponse(
                    text=data.get("response", ""),
                    provider=self.name,
                    model=model,
                    tokens_input=data.get("prompt_token_count", 0),
                    tokens_output=data.get("response_token_count", 0),
                    latency_ms=latency_ms,
                    metadata={
                        "total_duration": data.get("total_duration"),
                        "load_duration": data.get("load_duration"),
                        "eval_count": data.get("eval_count"),
                    },
                )
                
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using Ollama chat interface."""
        import httpx
        import time
        
        model = model or self.default_model
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False,
                        **kwargs,
                    },
                )
                
                if response.status_code != 200:
                    raise Exception(f"Ollama error: {response.status_code} - {response.text}")
                
                data = response.json()
                
                latency_ms = (time.time() - start_time) * 1000
                
                return LLMResponse(
                    text=data.get("message", {}).get("content", ""),
                    provider=self.name,
                    model=model,
                    tokens_input=data.get("prompt_token_count", 0),
                    tokens_output=data.get("response_token_count", 0),
                    latency_ms=latency_ms,
                    metadata={
                        "total_duration": data.get("total_duration"),
                        "load_duration": data.get("load_duration"),
                        "eval_count": data.get("eval_count"),
                    },
                )
                
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise


class GigaChatProvider(LLMProvider):
    """GigaChat LLM Provider."""

    def __init__(self):
        """Initialize GigaChat provider."""
        super().__init__("gigachat")
        self.client_id = settings.gigachat_client_id
        self.client_secret = settings.gigachat_client_secret
        self.auth_key = settings.gigachat_auth_key
        self.legacy_key = settings.gigachat_api_key
        self.api_url = settings.gigachat_url
        self.auth_url = settings.gigachat_auth_url
        self.scope = settings.gigachat_scope
        self.default_model = settings.gigachat_model
        self.access_token: Optional[str] = None

    def _basic_credentials(self) -> str:
        """Return the value to send as `Authorization: Basic <...>`."""
        if self.auth_key:
            return self.auth_key
        if self.client_id and self.client_secret:
            import base64

            raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
            return base64.b64encode(raw).decode("utf-8")
        if self.legacy_key:
            # Legacy mode treated the key as the client id
            return self.legacy_key
        return ""

    async def _get_access_token(self) -> str:
        """Get GigaChat access token."""
        if self.access_token:
            return self.access_token
        
        import httpx
        
        try:
            basic = self._basic_credentials()
            if not basic:
                raise Exception("GigaChat credentials are not configured")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.auth_url,
                    headers={
                        "Authorization": f"Basic {basic}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data=f"scope={self.scope}",
                )
                
                if response.status_code != 200:
                    raise Exception(f"GigaChat auth error: {response.status_code} - {response.text}")
                
                data = response.json()
                self.access_token = data.get("access_token")
                return self.access_token
                
        except Exception as e:
            logger.error(f"GigaChat auth error: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using GigaChat."""
        import httpx
        import time
        
        access_token = await self._get_access_token()
        model = model or self.default_model
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        **kwargs,
                    },
                )
                
                if response.status_code != 200:
                    raise Exception(f"GigaChat error: {response.status_code} - {response.text}")
                
                data = response.json()
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Extract usage info
                usage = data.get("usage", {})
                
                return LLMResponse(
                    text=data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    provider=self.name,
                    model=model,
                    tokens_input=usage.get("prompt_tokens", 0),
                    tokens_output=usage.get("completion_tokens", 0),
                    latency_ms=latency_ms,
                    metadata={
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                )
                
        except Exception as e:
            logger.error(f"GigaChat generation error: {e}")
            raise

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using GigaChat chat interface."""
        # GigaChat uses the same endpoint for chat
        return await self.generate(
            prompt=messages[-1]["content"] if messages else "",
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            **kwargs,
        )


class LLMManager:
    """Manages multiple LLM providers."""

    def __init__(self):
        """Initialize LLM manager."""
        self.providers: Dict[str, LLMProvider] = {
            "ollama": OllamaProvider(),
            "gigachat": GigaChatProvider(),
        }
        self.primary_provider = settings.llm_primary or settings.llm_provider
        if self.primary_provider not in self.providers:
            self.primary_provider = settings.llm_provider
        others = [name for name in self.providers if name != self.primary_provider]
        self.fallback_provider = settings.llm_fallback or (others[0] if others else None)

    def get_provider(self, provider_name: Optional[str] = None) -> LLMProvider:
        """Get LLM provider by name."""
        provider_name = provider_name or self.primary_provider
        
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return self.providers[provider_name]

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        provider: Optional[str] = None,
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using the specified provider."""
        try:
            provider_obj = self.get_provider(provider)
            return await provider_obj.generate(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Primary provider error: {e}")

            # Only infra errors (timeout/unavailable/5xx/network/rate-limit) fall back
            if use_fallback and self.fallback_provider and _is_retryable(e):
                try:
                    fallback_provider = self.get_provider(self.fallback_provider)
                    logger.info(f"Falling back to {self.fallback_provider}")
                    return await fallback_provider.generate(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                except Exception as fallback_error:
                    logger.error(f"Fallback provider error: {fallback_error}")
                    raise
            raise

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        provider: Optional[str] = None,
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text using chat interface."""
        try:
            provider_obj = self.get_provider(provider)
            return await provider_obj.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Primary provider chat error: {e}")

            if use_fallback and self.fallback_provider and _is_retryable(e):
                try:
                    fallback_provider = self.get_provider(self.fallback_provider)
                    logger.info(f"Falling back to {self.fallback_provider}")
                    return await fallback_provider.chat(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                except Exception as fallback_error:
                    logger.error(f"Fallback provider chat error: {fallback_error}")
                    raise
            raise
