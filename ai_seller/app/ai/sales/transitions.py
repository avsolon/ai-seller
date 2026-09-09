"""Sales state transition engine and intent routing.

Rule-based by design: the funnel is driven here, not by the LLM/RAG.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.sales import taxonomy
from app.ai.sales.state import SalesState
from app.ai.sales.taxonomy import CustomerIntent, SalesStage, funnel_stages

# Question templates asked by the agent, one per missing slot
QUESTION_TEMPLATES: Dict[str, str] = {
    "vehicle_make": "Подскажите марку автомобиля.",
    "vehicle_model": "Какая модель автомобиля?",
    "vehicle_year": "Какой год выпуска?",
    "headlight_type": "Какая сейчас оптика — галоген, ксенон или уже LED?",
    "current_lens": "Что сейчас стоит в фарах — штатные линзы или их уже меняли?",
    "primary_need": "Что хотите улучшить — яркость, дальность или ширину света?",
    "budget": "На какой бюджет ориентируетесь?",
    "installation_mode": "Установку будете делать сами или в сервисе?",
    "quantity": "Сколько комплектов нужно?",
    "delivery_city": "В какой город отправлять?",
}


def funnel_order() -> Dict[str, int]:
    """Map stage -> funnel index for progression checks."""
    return {stage: i for i, stage in enumerate(funnel_stages())}


def determine_next_stage(state: SalesState) -> SalesStage:
    """Decide the next stage based only on the accumulated state."""
    if state.handoff_requested:
        return SalesStage.HANDOFF
    if state.purchase.order_created:
        return SalesStage.ORDER
    if state.purchase.ready_to_buy:
        return SalesStage.CLOSING
    if any(not o.resolved for o in state.objections):
        return SalesStage.OBJECTION
    if state.selected_product is not None:
        return SalesStage.PRODUCT_SELECTION
    if not state.vehicle.is_identified:
        return SalesStage.DISCOVERY
    if not state.vehicle.compatibility_verified:
        return SalesStage.VEHICLE_QUALIFICATION
    if not state.need.primary_need:
        return SalesStage.NEED_IDENTIFIED
    return SalesStage.PRODUCT_SELECTION


def _slot_value(state: SalesState, slot: str) -> Optional[Any]:
    if slot == "vehicle_make":
        return state.vehicle.make
    if slot == "vehicle_model":
        return state.vehicle.model
    if slot == "vehicle_year":
        return state.vehicle.year
    if slot == "headlight_type":
        return state.vehicle.headlight_type
    if slot == "current_lens":
        return state.vehicle.current_lens
    if slot == "primary_need":
        return state.need.primary_need
    if slot == "budget":
        return state.need.budget
    if slot == "installation_mode":
        return state.purchase.installation_mode
    if slot == "quantity":
        return state.purchase.quantity
    if slot == "delivery_city":
        return state.purchase.delivery_city
    return None


def missing_slots(state: SalesState) -> List[str]:
    """Slots still required to advance, ordered by importance."""
    missing: List[str] = []

    for slot in ("vehicle_make", "vehicle_model", "vehicle_year"):
        if _slot_value(state, slot) is None:
            missing.append(slot)

    # Full vehicle info is a prerequisite for the following questions
    if not state.vehicle.is_identified:
        return missing

    # The client already decided to buy: only order-close slots remain.
    # Never bounce back to need/headlight/budget questions here.
    if state.purchase.ready_to_buy or state.purchase.order_created:
        if state.purchase.quantity is None:
            missing.append("quantity")
        if state.purchase.installation_mode is None:
            missing.append("installation_mode")
        if state.purchase.delivery_city is None and state.purchase.delivery_required:
            missing.append("delivery_city")
        return missing

    if state.need.primary_need is None:
        missing.append("primary_need")

    if not state.vehicle.compatibility_verified:
        if state.vehicle.headlight_type is None:
            missing.append("headlight_type")
        if state.vehicle.current_lens is None:
            missing.append("current_lens")

    if state.need.budget is None:
        missing.append("budget")

    return missing


def next_question(state: SalesState) -> Optional[str]:
    """Return the single best clarifying question for the current state."""
    state.missing_slots = missing_slots(state)
    for slot in state.missing_slots:
        template = QUESTION_TEMPLATES.get(slot)
        if template:
            return template
    return None


# --- Intent routing (what the agent should do for a given intent) ---------
def route_intent(intent: Optional[CustomerIntent]) -> Dict[str, Any]:
    """Map a customer intent to a processing strategy (RAG + tools)."""
    if intent is None:
        return {"retrieval": "sales", "tools": [], "expects_slots": []}

    strategy: Dict[str, Any] = {
        "retrieval": "sales",
        "tools": [],
        "expects_slots": [],
    }

    intent_map: Dict[CustomerIntent, Dict[str, Any]] = {
        CustomerIntent.GREETING: {"expects_slots": ["vehicle_make"]},
        CustomerIntent.VEHICLE_INFO: {"expects_slots": ["vehicle_make", "vehicle_model", "vehicle_year"]},
        CustomerIntent.NEED_DISCOVERY: {"expects_slots": ["primary_need"]},
        CustomerIntent.VEHICLE_COMPATIBILITY: {
            "retrieval": "knowledge",
            "tools": ["check_compatibility"],
            "expects_slots": ["headlight_type", "current_lens"],
        },
        CustomerIntent.PRODUCT_RECOMMENDATION: {
            "retrieval": "both",
            "tools": ["search_products", "get_price"],
            "expects_slots": ["primary_need", "budget"],
        },
        CustomerIntent.PRODUCT_COMPARISON: {
            "retrieval": "knowledge",
            "tools": ["search_products", "get_price"],
            "expects_slots": ["primary_need"],
        },
        CustomerIntent.PRICE_QUERY: {"tools": ["get_price"], "retrieval": "none"},
        CustomerIntent.PRICE_OBJECTION: {"tools": ["get_price"], "expects_slots": ["budget"]},
        CustomerIntent.TRUST_OBJECTION: {
            "retrieval": "knowledge",
            "tools": ["get_warranty", "get_delivery"],
        },
        CustomerIntent.DELIVERY_QUERY: {
            "retrieval": "knowledge",
            "tools": ["get_stock", "get_delivery"],
        },
        CustomerIntent.WARRANTY_QUERY: {"retrieval": "knowledge", "tools": ["get_warranty"]},
        CustomerIntent.INSTALLATION_QUERY: {
            "retrieval": "knowledge",
            "expects_slots": ["installation_mode"],
        },
        CustomerIntent.PURCHASE_INTENT: {
            "tools": ["create_order"],
            "expects_slots": ["quantity", "delivery_city"],
        },
        CustomerIntent.ORDER_REQUEST: {"tools": ["create_order"], "expects_slots": ["quantity"]},
        CustomerIntent.HESITATION: {"retrieval": "sales", "expects_slots": []},
        CustomerIntent.HANDOFF_REQUEST: {"tools": ["handoff"]},
    }
    strategy.update(intent_map.get(intent, {}))
    return strategy
