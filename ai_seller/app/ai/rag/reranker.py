"""Reranker with a combined score (doc 10): no cross-encoder on MVP.

final = 0.60*vector + 0.20*intent + 0.10*stage + 0.05*emotion + 0.05*quality
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.rag.query import RAGQuery

W_VECTOR = 0.60
W_INTENT = 0.20
W_STAGE = 0.10
W_EMOTION = 0.05
W_QUALITY = 0.05


def _norm(value: Optional[Any]) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value).strip().lower()


def _matches(expected: Optional[Any], actual: Optional[Any]) -> bool:
    if expected is None:
        return False
    return _norm(actual) == _norm(expected)


class Reranker:
    """Ranks retrieved chunks by combining the vector score with metadata matches."""

    def rerank(
        self, items: List[Dict[str, Any]], query: RAGQuery
    ) -> List[Dict[str, Any]]:
        ranked: List[Dict[str, Any]] = []
        for item in items:
            vector_score = float(item.get("score") or 0.0)
            quality = float(item.get("quality_score") or 0.0)
            final = (
                W_VECTOR * vector_score
                + W_INTENT * int(_matches(query.intent, item.get("intent")))
                + W_STAGE * int(_matches(query.stage, item.get("sales_stage")))
                + W_EMOTION * int(_matches(query.emotion, item.get("emotion")))
                + W_QUALITY * quality
            )
            payload = dict(item)
            payload["final_score"] = round(final, 4)
            ranked.append(payload)

        return sorted(ranked, key=lambda x: x["final_score"], reverse=True)
