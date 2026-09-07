"""RAGService (doc 10): retrieve candidates -> rerank -> top-k best chunks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.rag.query import RAGQuery
from app.ai.rag.reranker import Reranker

CACHE_TTL = 600  # 10 minutes


class RAGService:
    """Combines a retriever and a reranker for the sales knowledge lookup."""

    def __init__(
        self,
        retriever: Any,
        reranker: Optional[Reranker] = None,
        cache: Optional[Any] = None,
        top_k: int = 10,
        final_k: int = 5,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker or Reranker()
        self.cache = cache  # optional object with get(key)/set(key,value,ttl)
        self.top_k = top_k
        self.final_k = final_k

    def _cache_key(self, query: RAGQuery) -> str:
        return f"rag:{query.cache_key()}"

    async def retrieve(
        self,
        query: RAGQuery,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        key = self._cache_key(query)
        if self.cache is not None:
            cached = await self.cache.get(key)
            if cached is not None:
                return cached

        top_k = limit or self.top_k
        candidates = await self.retriever.search_sales_dialogues(
            query=query.text,
            intent=query.intent,
            sales_state=query.stage,
            customer_type=query.customer_type,
            limit=top_k,
        )
        ranked = self.reranker.rerank(candidates, query)
        final = ranked[: self.final_k]

        if self.cache is not None and final:
            await self.cache.set(key, final, CACHE_TTL)
        return final
