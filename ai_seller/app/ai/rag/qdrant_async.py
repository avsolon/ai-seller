"""AsyncQdrantClient wrapper exposing the classic `.search` interface.

Newer qdrant-client exposes async search via `query_points`; this subclass keeps
the project codebase working with a familiar `.search(...)` returning a plain
list of scored points.
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient as _AsyncQdrantClient


class AsyncQdrantClient(_AsyncQdrantClient):
    async def search(self, *, collection_name: str, query_vector, limit: int = 5,
                     with_payload: bool = True, with_vectors: bool = False,
                     query_filter=None):
        response = await self.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        return response.points
