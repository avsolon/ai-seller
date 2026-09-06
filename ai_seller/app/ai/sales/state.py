"""SalesState and its nested value objects.

Mirrors the documentation (7_SalesState_StateMachine.odt): the agent's single
source of truth about where a dialogue is and which slots are still missing.
RAG never drives the funnel; SalesState + transitions do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.ai.sales.taxonomy import (
    CustomerEmotion,
    CustomerIntent,
    CustomerType,
    SalesStage,
    coerce_intent,
    coerce_stage,
)


@dataclass
class VehicleState:
    """Facts known about the customer's car."""

    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    headlight_type: Optional[str] = None  # halogen | xenon | led | hid
    current_lens: Optional[str] = None
    photo_available: bool = False
    compatibility_verified: bool = False

    @property
    def is_identified(self) -> bool:
        return bool(self.make and self.model and self.year)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "headlight_type": self.headlight_type,
            "current_lens": self.current_lens,
            "photo_available": self.photo_available,
            "compatibility_verified": self.compatibility_verified,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VehicleState":
        return cls(
            make=data.get("make"),
            model=data.get("model"),
            year=data.get("year"),
            headlight_type=data.get("headlight_type"),
            current_lens=data.get("current_lens"),
            photo_available=bool(data.get("photo_available", False)),
            compatibility_verified=bool(data.get("compatibility_verified", False)),
        )


@dataclass
class NeedState:
    """What the customer wants to achieve."""

    primary_need: Optional[str] = None
    desired_result: Optional[str] = None
    current_problem: Optional[str] = None
    priorities: List[str] = field(default_factory=list)
    budget: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_need": self.primary_need,
            "desired_result": self.desired_result,
            "current_problem": self.current_problem,
            "priorities": list(self.priorities),
            "budget": str(self.budget) if self.budget is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NeedState":
        budget = data.get("budget")
        return cls(
            primary_need=data.get("primary_need"),
            desired_result=data.get("desired_result"),
            current_problem=data.get("current_problem"),
            priorities=list(data.get("priorities") or []),
            budget=Decimal(str(budget)) if budget not in (None, "") else None,
        )


@dataclass
class PurchaseState:
    """Order/purchase related facts."""

    quantity: Optional[int] = None
    installation_mode: Optional[str] = None  # self | installer | service_center
    delivery_required: Optional[bool] = None
    delivery_city: Optional[str] = None
    ready_to_buy: bool = False
    order_created: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quantity": self.quantity,
            "installation_mode": self.installation_mode,
            "delivery_required": self.delivery_required,
            "delivery_city": self.delivery_city,
            "ready_to_buy": self.ready_to_buy,
            "order_created": self.order_created,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PurchaseState":
        return cls(
            quantity=data.get("quantity"),
            installation_mode=data.get("installation_mode"),
            delivery_required=data.get("delivery_required"),
            delivery_city=data.get("delivery_city"),
            ready_to_buy=bool(data.get("ready_to_buy", False)),
            order_created=bool(data.get("order_created", False)),
        )


@dataclass
class ProductSelection:
    """Currently considered product."""

    product_id: Optional[str] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    price: Optional[Decimal] = None
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "sku": self.sku,
            "name": self.name,
            "price": str(self.price) if self.price is not None else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductSelection":
        price = data.get("price")
        return cls(
            product_id=data.get("product_id"),
            sku=data.get("sku"),
            name=data.get("name"),
            price=Decimal(str(price)) if price not in (None, "") else None,
            source=data.get("source"),
        )


@dataclass
class Objection:
    """Raised objection."""

    code: str  # PRICE | TRUST | COMPATIBILITY | INSTALLATION | DELIVERY | WARRANTY | COMPARISON | HESITATION
    text: str = ""
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "text": self.text, "resolved": self.resolved}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Objection":
        return cls(
            code=data.get("code", ""),
            text=data.get("text", ""),
            resolved=bool(data.get("resolved", False)),
        )


@dataclass
class SalesState:
    """Current state of the dialogue with a customer."""

    conversation_id: str
    stage: SalesStage = SalesStage.NEW
    intent: Optional[CustomerIntent] = None
    emotion: Optional[CustomerEmotion] = None
    customer_type: Optional[CustomerType] = None
    vehicle: VehicleState = field(default_factory=VehicleState)
    need: NeedState = field(default_factory=NeedState)
    purchase: PurchaseState = field(default_factory=PurchaseState)
    selected_product: Optional[ProductSelection] = None
    objections: List[Objection] = field(default_factory=list)
    last_customer_message: str = ""
    missing_slots: List[str] = field(default_factory=list)
    purchase_intent_score: float = 0.0
    handoff_requested: bool = False
    updated_at: Optional[str] = None

    def touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat()

    def add_objection(self, code: str, text: str = "") -> None:
        self.objections.append(Objection(code=code, text=text))
        self.touch()

    def mark_objection_resolved(self, code: str) -> None:
        for obj in self.objections:
            if obj.code == code:
                obj.resolved = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "stage": self.stage.value,
            "intent": self.intent.value if self.intent else None,
            "emotion": self.emotion.value if self.emotion else None,
            "customer_type": self.customer_type.value if self.customer_type else None,
            "vehicle": self.vehicle.to_dict(),
            "need": self.need.to_dict(),
            "purchase": self.purchase.to_dict(),
            "selected_product": self.selected_product.to_dict()
            if self.selected_product
            else None,
            "objections": [o.to_dict() for o in self.objections],
            "last_customer_message": self.last_customer_message,
            "missing_slots": list(self.missing_slots),
            "purchase_intent_score": self.purchase_intent_score,
            "handoff_requested": self.handoff_requested,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SalesState":
        stage_value = data.get("stage") or SalesStage.NEW.value
        state = cls(
            conversation_id=str(data.get("conversation_id", "")),
            stage=coerce_stage(stage_value),
            intent=coerce_intent(data["intent"]) if data.get("intent") else None,
            emotion=CustomerEmotion(data["emotion"]) if data.get("emotion") else None,
            customer_type=CustomerType(data["customer_type"])
            if data.get("customer_type")
            else None,
            vehicle=VehicleState.from_dict(data.get("vehicle") or {}),
            need=NeedState.from_dict(data.get("need") or {}),
            purchase=PurchaseState.from_dict(data.get("purchase") or {}),
            selected_product=ProductSelection.from_dict(data["selected_product"])
            if data.get("selected_product")
            else None,
            objections=[Objection.from_dict(o) for o in (data.get("objections") or [])],
            last_customer_message=data.get("last_customer_message", ""),
            missing_slots=list(data.get("missing_slots") or []),
            purchase_intent_score=float(data.get("purchase_intent_score", 0.0)),
            handoff_requested=bool(data.get("handoff_requested", False)),
            updated_at=data.get("updated_at"),
        )
        return state
