"""Sales state machine package: taxonomy, state, transitions, guard, evaluation."""

from app.ai.sales.taxonomy import (
    CustomerEmotion,
    CustomerIntent,
    CustomerType,
    SalesStage,
    load_taxonomy,
    taxonomy_exists,
)
from app.ai.sales.state import (
    NeedState,
    Objection,
    ProductSelection,
    PurchaseState,
    SalesState,
    VehicleState,
)
from app.ai.sales.transitions import (
    determine_next_stage,
    funnel_order,
    missing_slots,
    next_question,
    route_intent,
)
from app.ai.sales.service import (
    MemoryStateCache,
    RedisStateCache,
    SalesStateService,
    state_cache,
)

__all__ = [
    "SalesStage",
    "CustomerIntent",
    "CustomerEmotion",
    "CustomerType",
    "load_taxonomy",
    "taxonomy_exists",
    "SalesState",
    "VehicleState",
    "NeedState",
    "PurchaseState",
    "ProductSelection",
    "Objection",
    "determine_next_stage",
    "funnel_order",
    "missing_slots",
    "next_question",
    "route_intent",
    "SalesStateService",
    "MemoryStateCache",
    "RedisStateCache",
    "state_cache",
]
