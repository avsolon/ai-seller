"""Structured AgentResponse (doc 13): channels convert it to their own format.

Products/quick replies are derived from verified tool data — the LLM never
generates HTML or prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.sales.taxonomy import canonical_stage


@dataclass
class AgentResponse:
    text: str
    products: List[Dict[str, Any]] = field(default_factory=list)
    quick_replies: List[Dict[str, Any]] = field(default_factory=list)
    handoff: bool = False
    stage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "products": self.products,
            "quick_replies": self.quick_replies,
            "handoff": self.handoff,
            "stage": self.stage,
        }


def _find_tool(tools: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for tool in tools:
        if tool.get("tool") == name:
            return tool
    return None


def build_response(result: Dict[str, Any]) -> AgentResponse:
    """Convert the core processing result into a structured AgentResponse."""
    tools = result.get("tools") or []
    stage_raw = result.get("stage") or result.get("decision", {}).get("stage")

    products: List[Dict[str, Any]] = []
    search = _find_tool(tools, "search_products")
    if search and search.get("success"):
        raw = search.get("result") or {}
        for item in raw.get("products", []) if isinstance(raw, dict) else raw or []:
            products.append(
                {
                    "product_id": item.get("product_id") or item.get("id"),
                    "sku": item.get("sku"),
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "availability": {
                        "status": "in_stock",
                        "quantity": max(int(item.get("stock_quantity") or 0), 0) or None,
                    },
                    "actions": [{"type": "details", "label": "Подробнее"}, {"type": "select", "label": "Выбрать"}],
                }
            )

    return AgentResponse(
        text=result.get("reply", ""),
        products=products,
        quick_replies=_quick_replies(result.get("decision", {}).get("required_slots") or []),
        handoff=bool(result.get("handoff")),
        stage=canonical_stage(stage_raw) if stage_raw else None,
    )


def _quick_replies(required_slots: List[str]) -> List[Dict[str, Any]]:
    """Suggest quick answers only for closed-question slots (MVP)."""
    options = {
        "headlight_type": [
            {"id": "halogen", "label": "Галоген"},
            {"id": "xenon", "label": "Ксенон"},
            {"id": "led", "label": "LED"},
        ],
        "installation_mode": [
            {"id": "self", "label": "Буду ставить сам"},
            {"id": "service_center", "label": "В сервисе"},
        ],
    }
    replies = []
    for slot in required_slots[:1]:
        replies.extend(options.get(slot, []))
    return replies[:4]
