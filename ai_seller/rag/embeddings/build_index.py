"""Script to build and index Sales RAG dataset into Qdrant."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from app.ai.rag.qdrant_async import AsyncQdrantClient
from qdrant_client import models
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import get_logger

try:  # when run as a module (python -m rag.embeddings.build_index)
    from rag.embeddings import sales_dataset
except Exception:  # when run as a plain script from the embeddings directory
    import sales_dataset  # type: ignore

logger = get_logger(__name__)


class SalesRAGIndexer:
    """Index Sales RAG dataset into Qdrant."""

    def __init__(self):
        """Initialize the indexer."""
        self.qdrant_client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.collection_name = settings.qdrant_sales_collection
        
    async def initialize_collection(self) -> None:
        """Initialize Qdrant collection for sales dialogues."""
        try:
            # Check if collection exists
            collections = await self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                # Create new collection
                await self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=384,  # Size for paraphrase-multilingual-MiniLM-L12-v2
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created collection {self.collection_name}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")

            # Create payload indexes for filtered fields (idempotent best-effort)
            keyword_fields = [
                "id",
                "scenario",
                "customer_type",
                "sales_stage",
                "intent",
                "emotion",
                "goal",
                "label",
                "objection",
                "language",
                "shop_id",
            ]
            for field in keyword_fields:
                try:
                    await self.qdrant_client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception as e:
                    logger.debug(f"Payload index {field} skipped: {e}")

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

    async def _index_dialogue(self, dialogue_data: Dict[str, Any], shop_id: str) -> None:
        """Index a single dialogue into Qdrant."""
        try:
            # Create semantic query for embedding
            semantic_query = sales_dataset.create_semantic_query(dialogue_data)

            # Generate embedding
            embedding = self._generate_embedding(semantic_query)

            # Prepare payload
            payload = sales_dataset.build_payload(dialogue_data, shop_id)

            # Create point
            point = models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, str(dialogue_data.get("id")))),
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
