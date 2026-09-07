"""RAG layer tests: Reranker, RAGService + canonical taxonomy helpers."""

import pytest

from app.ai.rag import RAGQuery, RAGService, Reranker
from app.ai.sales.service import MemoryStateCache
from app.ai.sales.taxonomy import canonical_intent, canonical_stage, filter_value


class FakeRetriever:
    def __init__(self):
        self.calls = 0

    async def search_sales_dialogues(self, query=None, intent=None, sales_state=None,
                                     customer_type=None, limit=10):
        self.calls += 1
        return [
            {
                "id": "a",
                "intent": "price_objection",
                "sales_stage": "objection",
                "emotion": "skeptical",
                "quality_score": 0.9,
                "score": 0.8,
            },
            {
                "id": "b",
                "intent": "price_objection",
                "sales_stage": "objection",
                "emotion": "skeptical",
                "quality_score": 0.6,
                "score": 0.95,
            },
            {
                "id": "c",
                "intent": "greeting",
                "sales_stage": "new",
                "quality_score": 0.7,
                "score": 0.5,
            },
        ]


class TestCanonicalTaxonomy:
    def test_canonical_stage_intent(self):
        assert canonical_stage("discovery") == "DISCOVERY"
        assert canonical_stage("DISCOVERY") == "DISCOVERY"
        assert canonical_intent("price_objection") == "PRICE_OBJECTION"
        assert filter_value("OBJECTION") == "objection"


class TestReranker:
    def test_ranks_by_combined_score(self):
        reranker = Reranker()
        query = RAGQuery(text="Дорого", intent="PRICE_OBJECTION", stage="OBJECTION")
        items = [
            {
                "id": "a",
                "intent": "price_objection",
                "sales_stage": "objection",
                "emotion": "skeptical",
                "quality_score": 0.9,
                "score": 0.8,
            },
            {
                "id": "b",
                "intent": "price_objection",
                "sales_stage": "objection",
                "emotion": "skeptical",
                "quality_score": 0.6,
                "score": 0.95,
            },
        ]
        ranked = reranker.rerank(items, query)
        assert len(ranked) == 2
        assert all("final_score" in r for r in ranked)
        # descending by final score
        assert ranked[0]["final_score"] >= ranked[1]["final_score"]
        # intent+stage match bonuses apply to both -> vector dominates
        assert ranked[0]["id"] == "b"


class TestRAGService:
    async def test_retrieve_reranks_and_limits(self):
        retriever = FakeRetriever()
        service = RAGService(retriever=retriever, final_k=2)
        query = RAGQuery(text="Дорого", intent="PRICE_OBJECTION", stage="OBJECTION")
        result = await service.retrieve(query)
        assert retriever.calls == 1
        assert len(result) == 2
        assert "final_score" in result[0]

    async def test_cache_hit_skips_retriever(self):
        retriever = FakeRetriever()
        cache = MemoryStateCache()
        service = RAGService(retriever=retriever, cache=cache, final_k=2)
        query = RAGQuery(text="Дорого", intent="PRICE_OBJECTION", stage="OBJECTION")
        await service.retrieve(query)
        await service.retrieve(query)
        assert retriever.calls == 1
