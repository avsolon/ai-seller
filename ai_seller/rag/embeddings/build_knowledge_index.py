"""Build and index the Knowledge RAG (products, specs, FAQ, delivery, ...) into Qdrant.

Usage (after qdrant is up):
  python ai_seller/rag/embeddings/build_knowledge_index.py
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings
from app.core.logging import get_logger

try:  # when run as a module (python -m rag.embeddings.build_knowledge_index)
    from rag.embeddings import knowledge_builder
except Exception:  # when run as a plain script from the embeddings directory
    import knowledge_builder  # type: ignore

logger = get_logger(__name__)

EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2


class KnowledgeRAGIndexer:
    """Index the knowledge base into a Qdrant 'product_knowledge' collection."""

    def __init__(self) -> None:
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer

        self.qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.collection_name = settings.qdrant_knowledge_collection

    async def initialize_collection(self) -> None:
        from qdrant_client import models

        collections = await self.qdrant_client.get_collections()
        names = [c.name for c in collections.collections]
        if self.collection_name not in names:
            await self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=EMBEDDING_DIM, distance=models.Distance.COSINE
                ),
            )
            logger.info(f"Created collection {self.collection_name}")
        else:
            logger.info(f"Collection {self.collection_name} already exists")

        for field in ("shop_id", "source_type", "source"):
            try:
                await self.qdrant_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                logger.debug(f"Payload index {field} skipped: {e}")

    def _embed(self, text: str) -> List[float]:
        vector = self.embedding_model.encode(text, convert_to_tensor=True)
        return vector.tolist()

    async def index_records(self, records: List[Dict[str, Any]], shop_id: str) -> int:
        from qdrant_client import models

        points = []
        for record in records:
            vector = self._embed(record["text"])
            payload: Dict[str, Any] = {
                "id": record["id"],
                "title": record.get("title"),
                "content": record["text"],
                "source_type": record.get("source_type", "other"),
                "source": record.get("source"),
                "shop_id": shop_id,
            }
            points.append(
                models.PointStruct(
                    id=record["id"],
                    vector=vector,
                    payload=payload,
                )
            )
            if len(points) >= 100:
                await self.qdrant_client.upsert(
                    collection_name=self.collection_name, points=points
                )
                points = []

        if points:
            await self.qdrant_client.upsert(
                collection_name=self.collection_name, points=points
            )
        return len(records)


async def main() -> None:
    logger.info("Starting Knowledge RAG indexing...")
    script_dir = Path(__file__).resolve().parent
    knowledge_root = script_dir.parent / "knowledge"
    logger.info(f"Knowledge root: {knowledge_root}")

    records = list(knowledge_builder.gather_records(knowledge_root))
    logger.info(f"Collected {len(records)} knowledge records")

    indexer = KnowledgeRAGIndexer()
    await indexer.initialize_collection()
    await indexer.index_records(records, settings.shop_id)
    logger.info(f"Indexed {len(records)} knowledge records into {indexer.collection_name}")


if __name__ == "__main__":
    asyncio.run(main())
