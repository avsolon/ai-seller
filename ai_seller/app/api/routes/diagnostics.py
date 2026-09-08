"""Diagnostics endpoints: verify LLM (GigaChat) and RAG (Qdrant) are live."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

PING_TIMEOUT = 12.0


@router.get("/llm")
async def check_llm() -> dict:
    """Ping the configured LLM (primary provider, Ollama fallback)."""
    settings = get_settings()
    provider_name = settings.llm_primary or settings.llm_provider

    if provider_name == "openai":
        model_label = settings.openai_model
        configured = bool(settings.openai_base_url and settings.openai_api_key)
    elif provider_name == "gigachat":
        model_label = settings.gigachat_model
        configured = bool(settings.gigachat_auth_key or settings.gigachat_client_id)
    else:
        model_label = settings.ollama_default_model
        configured = True

    result = {
        "provider": provider_name,
        "fallback": settings.llm_fallback,
        "model": model_label,
        "configured": configured,
        "ok": False,
        "error": None,
        "sample": None,
    }
    try:
        from app.ai.llm.manager import LLMManager

        manager = LLMManager()

        async def _ping():
            return await manager.generate(
                prompt="Ответь одним словом: работаешь ли ты?",
                temperature=0.0,
                max_tokens=10,
            )

        response = await asyncio.wait_for(_ping(), timeout=PING_TIMEOUT)
        result.update(
            ok=True,
            provider=response.provider,
            model=response.model,
            sample=response.text[:100],
        )
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


@router.get("/rag")
async def check_rag() -> dict:
    """Report Qdrant collections and record counts for RAG."""
    settings = get_settings()
    collections = {
        "sales": settings.qdrant_sales_collection,
        "knowledge": settings.qdrant_knowledge_collection,
    }
    result = {"collections": {}, "error": None}
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        for role, name in collections.items():
            try:
                info = client.get_collection(name)
                count = info.points_count
                result["collections"][role] = {"name": name, "points": count}
            except Exception as e:
                result["collections"][role] = {"name": name, "error": str(e)}
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
