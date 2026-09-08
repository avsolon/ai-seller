"""RAG Retriever - retrieves relevant information from knowledge bases."""

from typing import Any, Dict, List, Optional

from app.ai.rag.qdrant_async import AsyncQdrantClient
from qdrant_client import models
from qdrant_client.http import models as qdrant_models

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RAGRetriever:
    """Retrieves relevant information from RAG knowledge bases."""

    def __init__(self):
        """Initialize the retriever."""
        self.qdrant_client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        self.knowledge_collection = settings.qdrant_knowledge_collection
        self.sales_collection = settings.qdrant_sales_collection
        self._embedding_model = None

    async def search_knowledge(
        self,
        query: str,
        intent: Optional[str] = None,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search in knowledge RAG (with graceful fallback to an unfiltered search)."""
        try:
            # Generate embedding for query
            embedding = self._generate_embedding(query)

            # Prepare filters
            qdrant_filters = self._prepare_filters(filters, intent)

            results = []
            if qdrant_filters is not None:
                search_result = await self.qdrant_client.search(
                    collection_name=self.knowledge_collection,
                    query_vector=embedding,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                    query_filter=qdrant_filters,
                )
                results = [r.payload for r in search_result]

            if not results:
                search_result = await self.qdrant_client.search(
                    collection_name=self.knowledge_collection,
                    query_vector=embedding,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                )
                results = [r.payload for r in search_result]

            return results

        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            return []

    async def search_sales_dialogues(
        self,
        query: str,
        intent: Optional[str] = None,
        sales_state: Optional[str] = None,
        customer_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search in sales dialogues RAG.

        First attempts a filtered search (intent / state / customer type) and
        gracefully falls back to an unfiltered semantic search when the strict
        filter matches nothing. This keeps retrieval robust even when the
        keyword-based intent detection does not exactly match the dataset
        taxonomy.
        """
        try:
            # Generate embedding for query
            embedding = self._generate_embedding(query)

            # Normalize filter values to lowercase to match indexed payloads
            def _norm(value: Optional[str]) -> Optional[str]:
                if not value:
                    return None
                return str(value).strip().lower()

            norm_intent = _norm(intent)
            norm_stage = _norm(sales_state)
            norm_customer = _norm(customer_type)

            # Soft cascade: intent+stage -> intent -> stage -> semantic (doc 10)
            steps: List[Optional[Dict[str, Optional[str]]]] = [
                {
                    "intent": norm_intent,
                    "sales_stage": norm_stage,
                    "customer_type": norm_customer,
                }
                if norm_intent or norm_stage or norm_customer
                else None,
                {"intent": norm_intent} if norm_intent else None,
                {"sales_stage": norm_stage} if norm_stage else None,
            ]

            results: List[Dict[str, Any]] = []
            for step in steps:
                filters = {"shop_id": settings.shop_id}
                if step:
                    filters.update({k: v for k, v in step.items() if v})
                qdrant_filters = self._prepare_filters(filters)

                search_result = await self.qdrant_client.search(
                    collection_name=self.sales_collection,
                    query_vector=embedding,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                    query_filter=qdrant_filters,
                )
                items = [
                    {**(dict(r.payload) if r.payload else {}), "score": r.score}
                    for r in search_result
                ]
                if items:
                    results = items
                    break

            return results

        except Exception as e:
            logger.error(f"Error searching sales dialogues: {e}")
            return []

    def _get_embedding_model(self):
        """Return a lazily-initialized, cached SentenceTransformer model."""
        if getattr(self, "_embedding_model", None) is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(settings.embedding_model)
        return self._embedding_model

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # In production, use proper embedding model
        # For now, return a dummy embedding
        model = self._get_embedding_model()
        embedding = model.encode(text, convert_to_tensor=True)
        return embedding.tolist()

    def _prepare_filters(
        self, filters: Optional[Dict[str, Any]], intent: Optional[str] = None
    ) -> Optional[qdrant_models.Filter]:
        """Prepare Qdrant filters from dictionary."""
        if not filters and not intent:
            return None
        
        # Combine filters
        all_filters = filters or {}
        if intent:
            all_filters["intent"] = intent
        
        # Remove None values
        all_filters = {k: v for k, v in all_filters.items() if v is not None}
        
        if not all_filters:
            return None
        
        # Create Qdrant filter conditions
        conditions = []
        for key, value in all_filters.items():
            if isinstance(value, str):
                conditions.append(
                    qdrant_models.FieldCondition(
                        key=key,
                        match=qdrant_models.MatchValue(value=value),
                    )
                )
            elif isinstance(value, (int, float)):
                conditions.append(
                    qdrant_models.FieldCondition(
                        key=key,
                        match=qdrant_models.MatchValue(value=value),
                    )
                )
            elif isinstance(value, list):
                conditions.append(
                    qdrant_models.FieldCondition(
                        key=key,
                        match=qdrant_models.MatchAny(any=value),
                    )
                )
        
        if len(conditions) == 1:
            return qdrant_models.Filter(must=conditions)
        elif len(conditions) > 1:
            return qdrant_models.Filter(must=conditions)
        
        return None

    async def get_knowledge_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific knowledge document by ID."""
        try:
            points, _ = await self.qdrant_client.scroll(
                collection_name=self.knowledge_collection,
                limit=1,
                with_payload=True,
                with_vectors=False,
                query_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="id",
                            match=qdrant_models.MatchValue(value=document_id),
                        )
                    ]
                ),
            )
            
            if points:
                return dict(points[0].payload or {})
            return None
            
        except Exception as e:
            logger.error(f"Error getting knowledge document: {e}")
            return None

    async def get_sales_dialogue(self, dialogue_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific sales dialogue by ID."""
        try:
            points, _ = await self.qdrant_client.scroll(
                collection_name=self.sales_collection,
                limit=1,
                with_payload=True,
                with_vectors=False,
                query_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="id",
                            match=qdrant_models.MatchValue(value=dialogue_id),
                        )
                    ]
                ),
            )
            
            if points:
                return dict(points[0].payload or {})
            return None
            
        except Exception as e:
            logger.error(f"Error getting sales dialogue: {e}")
            return None
