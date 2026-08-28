"""Script to build and index Sales RAG dataset into Qdrant."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SalesRAGIndexer:
    """Index Sales RAG dataset into Qdrant."""

    def __init__(self):
        """Initialize the indexer."""
        self.qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.collection_name = "sales_dialogues"
        
    async def initialize_collection(self) -> None:
        """Initialize Qdrant collection for sales dialogues."""
        try:
            # Check if collection exists
            collections = await self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name in collection_names:
                logger.info(f"Collection {self.collection_name} already exists")
                return
            
            # Create new collection
            await self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384,  # Size for paraphrase-multilingual-MiniLM-L12-v2
                    distance=models.Distance.COSINE,
                ),
                # Define payload schema
                payload_schema={
                    "id": models.PayloadSchemaType.KEYWORD,
                    "scenario": models.PayloadSchemaType.KEYWORD,
                    "customer_type": models.PayloadSchemaType.KEYWORD,
                    "sales_stage": models.PayloadSchemaType.KEYWORD,
                    "intent": models.PayloadSchemaType.KEYWORD,
                    "emotion": models.PayloadSchemaType.KEYWORD,
                    "objection": models.PayloadSchemaType.KEYWORD,
                    "goal": models.PayloadSchemaType.KEYWORD,
                    "quality_score": models.PayloadSchemaType.FLOAT,
                    "language": models.PayloadSchemaType.KEYWORD,
                    "shop_id": models.PayloadSchemaType.KEYWORD,
                    "tags": models.PayloadSchemaType.KEYWORD,
                    "dialogue": models.PayloadSchemaType.TEXT,
                    "successful_strategy": models.PayloadSchemaType.TEXT,
                    "mistakes_to_avoid": models.PayloadSchemaType.TEXT,
                },
            )
            logger.info(f"Created collection {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Error initializing collection: {e}")
            raise

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def _extract_dialogue_text(self, dialogue: List[Dict[str, Any]]) -> str:
        """Extract text from dialogue for embedding."""
        texts = []
        for message in dialogue:
            if message.get("role") == "customer":
                texts.append(f"Клиент: {message.get('text', '')}")
            elif message.get("role") == "seller":
                texts.append(f"Продавец: {message.get('text', '')}")
        return " ".join(texts)

    def _create_semantic_query(self, dialogue_data: Dict[str, Any]) -> str:
        """Create semantic query for embedding."""
        customer_type = dialogue_data.get("customer_profile", {}).get("type", "unknown")
        scenario = dialogue_data.get("scenario", "unknown")
        intent = dialogue_data.get("intent", "unknown")
        emotion = dialogue_data.get("emotion", "neutral")
        goal = dialogue_data.get("goal", "unknown")
        
        query = f"Клиент типа {customer_type} находится в сценарии {scenario} "
        query += f"с намерением {intent}, эмоцией {emotion} и целью {goal}. "
        query += f"Диалог: {self._extract_dialogue_text(dialogue_data.get('dialogue', []))}"
        
        return query

    async def _index_dialogue(self, dialogue_data: Dict[str, Any], shop_id: str) -> None:
        """Index a single dialogue into Qdrant."""
        try:
            # Create semantic query for embedding
            semantic_query = self._create_semantic_query(dialogue_data)
            
            # Generate embedding
            embedding = self._generate_embedding(semantic_query)
            
            # Prepare payload
            payload = {
                "id": dialogue_data.get("id"),
                "scenario": dialogue_data.get("scenario"),
                "customer_type": dialogue_data.get("customer_profile", {}).get("type"),
                "sales_stage": dialogue_data.get("sales_stage"),
                "intent": dialogue_data.get("intent"),
                "emotion": dialogue_data.get("emotion"),
                "objection": dialogue_data.get("objection"),
                "goal": dialogue_data.get("goal"),
                "quality_score": dialogue_data.get("quality_score", 0.0),
                "language": dialogue_data.get("language", "ru"),
                "shop_id": shop_id,
                "tags": dialogue_data.get("tags", []),
                "dialogue": json.dumps(dialogue_data.get("dialogue", []), ensure_ascii=False),
                "successful_strategy": json.dumps(dialogue_data.get("successful_strategy", []), ensure_ascii=False),
                "mistakes_to_avoid": json.dumps(dialogue_data.get("mistakes_to_avoid", []), ensure_ascii=False),
            }
            
            # Create point
            point = models.PointStruct(
                id=str(dialogue_data.get("id")),
                vector=embedding,
                payload=payload,
            )
            
            # Upsert point
            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
            
            logger.debug(f"Indexed dialogue {dialogue_data.get('id')}")
            
        except Exception as e:
            logger.error(f"Error indexing dialogue {dialogue_data.get('id')}: {e}")
            raise

    async def index_directory(self, directory_path: str, shop_id: str = "default-shop") -> int:
        """Index all JSONL files in a directory."""
        indexed_count = 0
        
        try:
            # Initialize collection
            await self.initialize_collection()
            
            # Process all JSONL files
            path = Path(directory_path)
            for jsonl_file in path.glob("**/*.jsonl"):
                logger.info(f"Processing file: {jsonl_file}")
                
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                            
                        try:
                            dialogue_data = json.loads(line)
                            await self._index_dialogue(dialogue_data, shop_id)
                            indexed_count += 1
                            
                            if indexed_count % 10 == 0:
                                logger.info(f"Indexed {indexed_count} dialogues so far...")
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing JSON in {jsonl_file}: {e}")
                        except Exception as e:
                            logger.error(f"Error indexing dialogue from {jsonl_file}: {e}")
            
            logger.info(f"Successfully indexed {indexed_count} dialogues")
            return indexed_count
            
        except Exception as e:
            logger.error(f"Error indexing directory: {e}")
            raise

    async def search_similar(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar dialogues."""
        try:
            # Generate embedding for query
            embedding = self._generate_embedding(query)
            
            # Search in Qdrant
            search_result = await self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=embedding,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            
            # Convert results to list of dictionaries
            results = []
            for result in search_result:
                results.append(result.payload)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching similar dialogues: {e}")
            raise


async def main():
    """Main function to index Sales RAG dataset."""
    logger.info("Starting Sales RAG indexing...")
    
    try:
        # Create indexer
        indexer = SalesRAGIndexer()
        
        # Get the path to seller_dialogues directory
        script_dir = Path(__file__).parent
        seller_dialogues_dir = script_dir.parent / "seller_dialogues"
        
        logger.info(f"Indexing dialogues from: {seller_dialogues_dir}")
        
        # Index all dialogues
        count = await indexer.index_directory(seller_dialogues_dir, settings.shop_id)
        
        logger.info(f"Indexing complete. Total dialogues indexed: {count}")
        
        # Test search
        test_query = "Клиент говорит что дорого и хочет более дешевый вариант"
        logger.info(f"Testing search with query: {test_query}")
        
        results = await indexer.search_similar(test_query, limit=3)
        logger.info(f"Found {len(results)} similar dialogues:")
        for result in results:
            logger.info(f"  - {result.get('id')}: {result.get('scenario')} - {result.get('intent')}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
