"""RAGQuery: retrieval query built from the current SalesState (doc 10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RAGQuery:
    """What to retrieve and how to filter it."""

    text: str
    stage: Optional[str] = None
    intent: Optional[str] = None
    emotion: Optional[str] = None
    customer_type: Optional[str] = None

    def cache_key(self) -> str:
        parts = [self.text.strip().lower()]
        for value in (self.stage, self.intent, self.emotion, self.customer_type):
            parts.append(str(value or "").strip().lower())
        return "|".join(parts)
