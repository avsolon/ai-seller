"""Deterministic catalog tools (Phase 4): facts come from the DB, not the LLM.

Each function returns a plain JSON-safe payload ready to be embedded in the
prompt and stored in the tool_calls audit table.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models.product import Compatibility, Product, Vehicle


async def search_products(
    db: AsyncSession,
    budget: Optional[float] = None,
    shop_id: Optional[UUID] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    query = select(Product).where(Product.is_active.is_(True))
    if shop_id is not None:
        query = query.where(Product.shop_id == shop_id)
    if budget is not None:
        query = query.where(Product.price <= budget)
    query = query.order_by(Product.price).limit(limit)
    products = (await db.execute(query)).scalars().all()
    return [
        {
            "product_id": str(p.id),
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "price": float(p.price) if p.price is not None else None,
            "stock_quantity": p.stock_quantity,
        }
        for p in products
    ]


async def get_product(
    db: AsyncSession, product_id: UUID
) -> Optional[Dict[str, Any]]:
    product = await db.get(Product, product_id)
    if product is None:
        return None
    return {
        "product_id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "specifications": product.specifications or {},
    }


async def get_price(
    db: AsyncSession, product_id: UUID
) -> Optional[Dict[str, Any]]:
    product = await db.get(Product, product_id)
    if product is None:
        return None
    return {
        "product_id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "price": float(product.price) if product.price is not None else None,
        "currency": product.currency,
    }


async def get_stock(
    db: AsyncSession, product_id: UUID
) -> Optional[Dict[str, Any]]:
    product = await db.get(Product, product_id)
    if product is None:
        return None
    return {
        "product_id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "stock_quantity": product.stock_quantity,
    }


async def check_compatibility(
    db: AsyncSession,
    make: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """Return confirmed compatibility rows for a vehicle (or empty facts)."""
    vehicle_identified = bool(make and model)

    matches: List[Dict[str, Any]] = []
    if vehicle_identified:
        vehicle_q = select(Vehicle).where(Vehicle.brand.ilike(f"%{make}%"))
        if model:
            vehicle_q = vehicle_q.where(Vehicle.model.ilike(f"%{model}%"))
        if year:
            vehicle_q = vehicle_q.where(
                (Vehicle.year_from.is_(None)) | (Vehicle.year_from <= year)
            )
        vehicles = (await db.execute(vehicle_q)).scalars().all()
        if vehicles:
            result = await db.execute(
                select(Compatibility)
                .where(
                    Compatibility.vehicle_id.in_([v.id for v in vehicles]),
                    Compatibility.is_confirmed.is_(True),
                )
                .options(selectinload(Compatibility.product))
            )
            for c in result.scalars().all():
                product = c.product
                matches.append(
                    {
                        "product_id": str(c.product_id),
                        "product_name": product.name if product else None,
                        "type": c.type,
                        "notes": c.notes,
                    }
                )

    return {
        "verified": bool(matches),
        "vehicle_identified": vehicle_identified,
        "matches": matches[:5],
    }
