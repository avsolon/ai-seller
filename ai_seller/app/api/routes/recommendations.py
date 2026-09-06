"""Recommendation routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.api.schemas import RecommendationRequest
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.product import Compatibility, Product, Vehicle
from app.infrastructure.database.models.sales import Recommendation, RecommendationSource
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _serialize_product(product: Product) -> dict:
    """Serialize a product to a plain dict."""
    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "price": float(product.price) if product.price is not None else None,
        "currency": product.currency,
        "stock_quantity": product.stock_quantity,
        "specifications": product.specifications or {},
    }


@router.post("/")
async def get_recommendations(
    request: RecommendationRequest,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Return rule-based product recommendations and optionally persist them."""
    shop = await resolve_shop(db, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    query = select(Product).where(Product.shop_id == shop.id, Product.is_active.is_(True))

    if request.category:
        query = query.where(Product.category == request.category)

    # Restrict to products compatible with the given vehicle when possible
    if request.vehicle_brand or request.vehicle_model:
        vehicle_q = select(Vehicle.id)
        if request.vehicle_brand:
            vehicle_q = vehicle_q.where(Vehicle.brand.ilike(f"%{request.vehicle_brand}%"))
        if request.vehicle_model:
            vehicle_q = vehicle_q.where(Vehicle.model.ilike(f"%{request.vehicle_model}%"))
        compatible_products = (
            select(Compatibility.product_id)
            .where(Compatibility.vehicle_id.in_(vehicle_q))
            .where(Compatibility.is_confirmed.is_(True))
        )
        query = query.where(Product.id.in_(compatible_products))

    if request.budget_min is not None:
        query = query.where(Product.price >= request.budget_min)
    if request.budget_max is not None:
        query = query.where(Product.price <= request.budget_max)

    query = query.order_by(Product.price).limit(request.limit)
    products = (await db.execute(query)).scalars().all()

    results = [_serialize_product(p) for p in products]

    # Persist recommendations when a conversation is provided
    saved_ids: List[str] = []
    if request.conversation_id and products:
        conversation = await db.get(Conversation, request.conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        for product in products:
            rec = Recommendation(
                conversation_id=conversation.id,
                customer_id=conversation.customer_id,
                product_id=product.id,
                reason="rule_based_matching",
                source=RecommendationSource.RULE,
            )
            db.add(rec)
            saved_ids.append(str(product.id))
        await db.flush()

    return {
        "recommendations": results,
        "count": len(results),
        "saved_product_ids": saved_ids,
    }
