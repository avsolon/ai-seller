"""AgentDecision: deterministic output of the sales controller.

The LLM is only used for NLU and response generation. Everything about what to do
next (stage, slots, tools, RAG strategy) is decided here, in code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.sales.taxonomy import CustomerIntent, SalesStage


@dataclass
class AgentDecision:
    """What the agent decided to do for the current customer message."""

    intent: Optional[CustomerIntent] = None
    stage: SalesStage = SalesStage.NEW
    next_stage: Optional[SalesStage] = None
    required_slots: List[str] = field(default_factory=list)
    tool_calls: List[str] = field(default_factory=list)
    rag_query: Optional[str] = None
    response_strategy: str = "general"
    handoff: bool = False
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value if self.intent else None,
            "stage": self.stage.value,
            "next_stage": self.next_stage.value if self.next_stage else None,
            "required_slots": list(self.required_slots),
            "tool_calls": list(self.tool_calls),
            "rag_query": self.rag_query,
            "response_strategy": self.response_strategy,
            "handoff": self.handoff,
            "confidence": self.confidence,
        }
