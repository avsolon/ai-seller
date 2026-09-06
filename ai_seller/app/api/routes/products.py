"""Product routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.infrastructure.database.models.product import Compatibility, Product
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _serialize_product(product: Product) -> dict:
    """Serialize a product to a plain dict."""
    return {
        "id": str(product.id),
        "shop_id": str(product.shop_id),
        "sku": product.sku,
        "name": product.name,
        "slug": product.slug,
        "brand": product.brand,
        "category": product.category,
        "description": product.description,
        "price": float(product.price) if product.price is not None else None,
        "currency": product.currency,
        "stock_quantity": product.stock_quantity,
        "specifications": product.specifications or {},
        "is_active": product.is_active,
    }


def _serialize_compatibility(item: Compatibility) -> dict:
    """Serialize a compatibility record to a plain dict."""
    vehicle = item.vehicle
    return {
        "id": str(item.id),
        "product_id": str(item.product_id),
        "vehicle_id": str(item.vehicle_id) if item.vehicle_id else None,
        "type": item.type,
        "notes": item.notes,
        "is_confirmed": item.is_confirmed,
        "vehicle": {
            "brand": vehicle.brand if vehicle else None,
            "model": vehicle.model if vehicle else None,
            "generation": vehicle.generation if vehicle else None,
        },
    }


@router.get("/")
async def list_products(
    db: DatabaseSession,
    shop_id: ShopId,
    search: Optional[str] = Query(None, description="Search by name/sku/brand/category"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
) -> dict:
    """List active products."""
    shop = await resolve_shop(db, shop_id)
    query = select(Product).where(Product.is_active.is_(True))
    if shop is not None:
        query = query.where(Product.shop_id == shop.id)

    if category:
        query = query.where(Product.category == category)

    if search:
        like = f"%{search.lower()}%"
        query = query.where(
            or_(
                Product.name.ilike(like),
                Product.sku.ilike(like),
                Product.brand.ilike(like),
                Product.category.ilike(like),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Product.category, Product.price).offset(offset).limit(limit)
    products = (await db.execute(query)).scalars().all()

    return {
        "products": [_serialize_product(p) for p in products],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Get a specific product."""
    shop = await resolve_shop(db, shop_id)
    query = select(Product).where(Product.id == product_id)
    if shop is not None:
        query = query.where(Product.shop_id == shop.id)

    product = (await db.execute(query)).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    return _serialize_product(product)


@router.get("/{product_id}/compatibility")
async def get_product_compatibility(
    product_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Get compatibility information for a product."""
    shop = await resolve_shop(db, shop_id)
    query = select(Product).where(Product.id == product_id)
    if shop is not None:
        query = query.where(Product.shop_id == shop.id)

    product = (await db.execute(query)).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    result = await db.execute(
        select(Compatibility)
        .where(Compatibility.product_id == product.id)
        .options(selectinload(Compatibility.vehicle))
    )
    items = result.scalars().all()

    return {
        "product_id": str(product.id),
        "product_name": product.name,
        "compatibilities": [_serialize_compatibility(item) for item in items],
        "count": len(items),
    }
