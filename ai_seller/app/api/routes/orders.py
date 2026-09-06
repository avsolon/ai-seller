"""Order routes."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.api.schemas import OrderCreate
from app.core.config import settings
from app.infrastructure.database.models.conversation import Conversation, SalesState
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.sales import Order, OrderItem, OrderStatus
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _serialize_order(order: Order) -> dict:
    """Serialize an order to a plain dict."""
    return {
        "id": str(order.id),
        "shop_id": str(order.shop_id),
        "customer_id": str(order.customer_id),
        "conversation_id": str(order.conversation_id),
        "status": order.status,
        "total_amount": float(order.total_amount) if order.total_amount is not None else 0.0,
        "currency": order.currency,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "id": str(item.id),
                "product_id": str(item.product_id),
                "variant_id": str(item.variant_id) if item.variant_id else None,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price) if item.unit_price is not None else None,
                "total_price": float(item.total_price) if item.total_price is not None else None,
            }
            for item in order.items
        ],
    }


@router.post("/")
async def create_order(
    request: OrderCreate,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Create a draft order request (MVP: no payments)."""
    shop = await resolve_shop(db, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    conversation = await db.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    total = Decimal("0.00")
    items: list[OrderItem] = []
    for item in request.items:
        product = await db.get(Product, item.product_id)
        if product is None or product.shop_id != shop.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item.product_id} not found in shop",
            )
        unit_price = Decimal(str(product.price))
        line_total = unit_price * item.quantity
        total += line_total
        items.append(
            OrderItem(
                product_id=product.id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                unit_price=unit_price,
                total_price=line_total,
            )
        )

    order = Order(
        shop_id=shop.id,
        customer_id=conversation.customer_id,
        conversation_id=conversation.id,
        status=OrderStatus.DRAFT,
        total_amount=total,
        currency=settings.default_currency,
        customer_name=request.customer_name,
        customer_phone=request.customer_phone,
        delivery_city=request.delivery_city,
    )
    db.add(order)
    await db.flush()
    order.items = items

    conversation.sales_state = SalesState.ORDER
    await db.flush()

    logger.info(f"Created order {order.id} total={total}")
    return _serialize_order(order)


@router.get("/")
async def list_orders(
    db: DatabaseSession,
    shop_id: ShopId,
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
) -> dict:
    """List orders."""
    shop = await resolve_shop(db, shop_id)
    query = select(Order)
    if shop is not None:
        query = query.where(Order.shop_id == shop.id)
    if customer_id:
        query = query.where(Order.customer_id == customer_id)

    orders = (await db.execute(query)).scalars().all()
    return {
        "orders": [_serialize_order(order) for order in orders],
        "total": len(orders),
    }
