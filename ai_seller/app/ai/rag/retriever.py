"""RAG Retriever - retrieves relevant information from knowledge bases."""

from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http import models as qdrant_models

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RAGRetriever:
    """Retrieves relevant information from RAG knowledge bases."""

    def __init__(self):
        """Initialize the retriever."""
        self.qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        self.knowledge_collection = "product_knowledge"
        self.sales_collection = "sales_dialogues"

    async def search_knowledge(
        self,
        query: str,
        intent: Optional[str] = None,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search in knowledge RAG."""
        try:
            # Generate embedding for query
            embedding = self._generate_embedding(query)
            
            # Prepare filters
            qdrant_filters = self._prepare_filters(filters, intent)
            
            # Search in Qdrant
            search_result = await self.qdrant_client.search(
                collection_name=self.knowledge_collection,
                query_vector=embedding,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                query_filter=qdrant_filters,
            )
            
            # Convert results
            results = []
            for result in search_result:
                results.append(result.payload)
            
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
        """Search in sales dialogues RAG."""
        try:
            # Generate embedding for query
            embedding = self._generate_embedding(query)
            
            # Prepare filters
            filters = {
                "intent": intent,
                "sales_stage": sales_state,
                "customer_type": customer_type,
                "shop_id": settings.shop_id,
            }
            qdrant_filters = self._prepare_filters(filters)
            
            # Search in Qdrant
            search_result = await self.qdrant_client.search(
                collection_name=self.sales_collection,
                query_vector=embedding,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                query_filter=qdrant_filters,
            )
            
            # Convert results
            results = []
            for result in search_result:
                results.append(result.payload)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching sales dialogues: {e}")
            return []

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # In production, use proper embedding model
        # For now, return a dummy embedding
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(settings.embedding_model)
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
            result = await self.qdrant_client.scroll(
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
            
            if result[0]:
                return result[0].payload
            return None
            
        except Exception as e:
            logger.error(f"Error getting knowledge document: {e}")
            return None

    async def get_sales_dialogue(self, dialogue_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific sales dialogue by ID."""
        try:
            result = await self.qdrant_client.scroll(
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
            
            if result[0]:
                return result[0].payload
            return None
            
        except Exception as e:
            logger.error(f"Error getting sales dialogue: {e}")
            return None
