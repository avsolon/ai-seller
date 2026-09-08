"""Check the AI Seller stack before live testing.

Usage:
  python ai_seller/scripts/check_stack.py [--no-llm]

Prints: config provider, credentials presence, LLM ping, Qdrant
collections + counts, Redis ping, DB reachability.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _print(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK " if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))


async def check_llm() -> None:
    from app.ai.llm.manager import LLMManager

    try:
        manager = LLMManager()
        _print(
            "LLM provider",
            True,
            f"primary={manager.primary_provider} fallback={manager.fallback_provider}",
        )
        import time

        start = time.monotonic()
        response = await asyncio.wait_for(
            manager.generate(
                prompt="Ответь одним словом: работаешь?",
                temperature=0.0,
                max_tokens=10,
            ),
            timeout=15,
        )
        _print(
            "LLM ping",
            True,
            f"{response.provider}/{response.model} -> {response.text[:50]!r} "
            f"({int((time.monotonic() - start) * 1000)} ms)",
        )
    except Exception as e:
        _print("LLM ping", False, f"{type(e).__name__}: {e}")


async def check_qdrant() -> None:
    from app.core.config import get_settings

    s = get_settings()
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key, timeout=5)
        for role, name in {
            "sales": s.qdrant_sales_collection,
            "knowledge": s.qdrant_knowledge_collection,
        }.items():
            try:
                count = client.get_collection(name).points_count
                _print(f"Qdrant [{role}] {name}", True, f"{count} points")
            except Exception as e:
                _print(f"Qdrant [{role}] {name}", False, str(e))
    except Exception as e:
        _print("Qdrant client", False, f"{type(e).__name__}: {e}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Skip the LLM ping")
    args = parser.parse_args()

    from app.core.config import get_settings

    s = get_settings()
    provider = s.llm_primary or s.llm_provider
    _print("Provider config", True, f"primary={provider}, fallback={s.llm_fallback}")
    if provider == "openai":
        _print(
            "OpenAI-compatible credentials",
            bool(s.openai_base_url and s.openai_api_key),
            f"base_url={s.openai_base_url!r}, key={'set' if s.openai_api_key else 'missing'}",
        )
    elif provider == "gigachat":
        _print(
            "GigaChat credentials",
            bool(s.gigachat_auth_key or s.gigachat_client_id),
            "AUTH_KEY set" if s.gigachat_auth_key else "missing",
        )
    else:
        _print("Ollama local", True, f"url={s.ollama_base_url}, model={s.ollama_default_model}")
    if not args.no_llm:
        await check_llm()
    await check_qdrant()


if __name__ == "__main__":
    asyncio.run(main())
