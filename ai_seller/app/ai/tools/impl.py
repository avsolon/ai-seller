"""Concrete business tools for the MVP (doc 11).

All tools return only verified data from PostgreSQL or store policy; they never
invent price/stock/warranty/delivery/compatibility.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from app.ai.tools import catalog_tools
from app.ai.tools.base import ToolContext, ToolResult
from app.ai.tools.registry import ToolRegistry
from app.core.config import settings
from app.infrastructure.database.models.sales import Lead, LeadStatus, Order, OrderStatus

_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "rag" / "knowledge"


@lru_cache(maxsize=None)
def _policy_text(rel_path: str) -> str:
    path = _KNOWLEDGE_ROOT / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


class GetProductTool:
    name = "get_product"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        product_id = arguments.get("product_id")
        if not product_id:
            return ToolResult(False, error="product_id required")
        payload = await catalog_tools.get_product(context.db, product_id)
        if payload is None:
            return ToolResult(False, error="product not found")
        return ToolResult(True, data=payload)


class SearchProductsTool:
    name = "search_products"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        budget = arguments.get("budget")
        category = arguments.get("category")
        products = await catalog_tools.search_products(
            context.db,
            budget=float(budget) if budget is not None else None,
            shop_id=context.conversation.shop_id,
            limit=arguments.get("limit", 3),
        )
        if category:
            products = [p for p in products if (p.get("category") or "") == category]
        return ToolResult(True, data={"products": products})


class GetProductPriceTool:
    name = "get_product_price"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        product_id = arguments.get("product_id")
        if not product_id:
            return ToolResult(False, error="product_id required")
        payload = await catalog_tools.get_price(context.db, product_id)
        if payload is None:
            return ToolResult(False, error="product not found")
        return ToolResult(True, data=payload)


class GetProductStockTool:
    name = "get_product_stock"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        product_id = arguments.get("product_id")
        if not product_id:
            return ToolResult(False, error="product_id required")
        payload = await catalog_tools.get_stock(context.db, product_id)
        if payload is None:
            return ToolResult(False, error="product not found")
        return ToolResult(True, data=payload)


class CheckCompatibilityTool:
    name = "check_compatibility"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        state = context.state
        payload = await catalog_tools.check_compatibility(
            context.db,
            make=state.vehicle.make,
            model=state.vehicle.model,
            year=state.vehicle.year,
        )
        if payload.get("verified"):
            data = {
                "verified": True,
                "vehicle": {
                    "make": state.vehicle.make,
                    "model": state.vehicle.model,
                    "year": state.vehicle.year,
                },
                "compatibility": "confirmed",
                "source": "verified_fitment",
                "matches": payload["matches"],
            }
            return ToolResult(True, data=data)

        required = []
        if state.vehicle.headlight_type is None:
            required.append("headlight_type")
        if not state.vehicle.photo_available:
            required.append("photo")
        return ToolResult(
            True,
            data={
                "verified": False,
                "reason": "headlight_type_required" if required else "no_confirmed_fitment",
                "required": required,
            },
        )


class GetDeliveryInfoTool:
    name = "get_delivery_info"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        text = _policy_text("delivery/terms.md")
        return ToolResult(
            True,
            data={"source": "store_policy", "policy": text[:2500]},
        )


class GetWarrantyInfoTool:
    name = "get_warranty_info"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        text = _policy_text("warranty/terms.md")
        return ToolResult(
            True,
            data={"source": "store_policy", "policy": text[:2500]},
        )


class CreateLeadTool:
    name = "create_lead"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        lead = Lead(
            shop_id=context.conversation.shop_id,
            customer_id=context.conversation.customer_id,
            conversation_id=context.conversation.id,
            status=LeadStatus.NEW,
            source=arguments.get("source") or "ai_agent",
        )
        context.db.add(lead)
        await context.db.flush()
        return ToolResult(True, data={"lead_id": str(lead.id)})


class CreateOrderTool:
    name = "create_order"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        order = Order(
            shop_id=context.conversation.shop_id,
            customer_id=context.conversation.customer_id,
            conversation_id=context.conversation.id,
            status=OrderStatus.DRAFT,
            total_amount=0,
            currency=settings.default_currency,
            delivery_city=arguments.get("delivery_city"),
        )
        context.db.add(order)
        await context.db.flush()
        return ToolResult(True, data={"order_id": str(order.id)})


class RequestHandoffTool:
    name = "request_handoff"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        context.state.handoff_requested = True
        return ToolResult(True, data={"handoff": True})


def build_default_registry() -> ToolRegistry:
    """Build a registry with all MVP business tools."""
    registry = ToolRegistry()
    registry.register_many(
        [
            GetProductTool(),
            SearchProductsTool(),
            GetProductPriceTool(),
            GetProductStockTool(),
            CheckCompatibilityTool(),
            GetDeliveryInfoTool(),
            GetWarrantyInfoTool(),
            CreateLeadTool(),
            CreateOrderTool(),
            RequestHandoffTool(),
        ]
    )
    return registry
