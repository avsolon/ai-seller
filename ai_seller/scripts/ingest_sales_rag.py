"""Ingest the Sales RAG dataset into Qdrant (doc 10).

Pipeline: JSONL -> validate -> normalize/payload -> embeddings -> Qdrant.
Requires qdrant-client + sentence-transformers (the embedding stack).

Usage:
  python ai_seller/scripts/ingest_sales_rag.py [--dir PATH] [--reset]
"""

import argparse
import asyncio
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = SCRIPT_DIR.parent / "rag" / "seller_dialogues"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Sales RAG dataset into Qdrant")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="Directory with *.jsonl")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate the collection before indexing",
    )
    args = parser.parse_args()

    from qdrant_client import QdrantClient, models

    from rag.embeddings import sales_dataset

    data_dir = Path(args.dir)
    records = []
    errors = []
    for path in sorted(data_dir.glob("**/*.jsonl")):
        for record in sales_dataset.iter_dataset(path):
            problems = sales_dataset.validate_record(record)
            if problems:
                errors.append({"file": str(path), "id": record.get("id"), "problems": problems})
            else:
                records.append(record)
    logger.info(f"Valid records: {len(records)}; invalid: {len(errors)}")
    for err in errors[:10]:
        logger.warning(f"Invalid {err}")

    client = QdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout
    )
    collection = settings.qdrant_sales_collection
    if args.reset:
        existing = [c.name for c in (await client.get_collections()).collections]
        if collection in existing:
            await client.delete_collection(collection)
            logger.info(f"Dropped collection {collection}")

    names = [c.name for c in (await client.get_collections()).collections]
    if collection not in names:
        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(
                size=384, distance=models.Distance.COSINE
            ),
        )

    # Import lazily so validation works without the qdrant stack
    from rag.embeddings.build_index import SalesRAGIndexer

    indexer = SalesRAGIndexer()
    indexer.collection_name = collection
    indexed = await indexer.index_directory(str(data_dir), settings.shop_id)
    logger.info(f"Ingestion finished: {indexed} records in {collection}")


if __name__ == "__main__":
    asyncio.run(main())
