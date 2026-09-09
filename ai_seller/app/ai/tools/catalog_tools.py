"""Deterministic catalog tools (Phase 4): facts come from the DB, not the LLM.

Each function returns a plain JSON-safe payload ready to be embedded in the
prompt and stored in the tool_calls audit table.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models.product import Compatibility, Product, Vehicle

_RU_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_RU_BRAND_OVERRIDES = {
    "бмв": "bmw",
    "хёндай": "hyundai",
    "хендай": "hyundai",
    "кия": "kia",
    "мерседес бенц": "mercedes-benz",
    "ленд ровер": "land rover",
    "лендровер": "land rover",
}


def _brand_variants(make: Optional[str]) -> List[str]:
    """Candidate spellings to match a DB vehicle brand (raw + transliterated)."""
    if not make:
        return []
    raw = str(make).strip().lower()
    if not raw:
        return []
    variants = [raw]
    latin = _RU_BRAND_OVERRIDES.get(raw)
    if latin is None:
        latin = "".join(_RU_TO_LATIN.get(ch, ch) for ch in raw).strip()
    if latin and latin != raw:
        variants.append(latin)
    return variants


async def search_products(
    db: AsyncSession,
    budget: Optional[float] = None,
    shop_id: Optional[UUID] = None,
    limit: int = 3,
    make: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return active products (cheapest first).

    When make+model are given, restrict to products with confirmed
    compatibility for the matching vehicle generation(s). If no vehicle was
    specified OR no confirmed fitment exists (model not in DB / no verified
    compatibility), return the global assortment so the consultant can still
    sell — those rows are flagged confirmed_for_vehicle=False and the LLM is
    told never to claim verified compatibility for them.
    """
    base = select(Product).where(Product.is_active.is_(True))
    if shop_id is not None:
        base = base.where(Product.shop_id == shop_id)
    if budget is not None:
        base = base.where(Product.price <= budget)

    compatible = False
    if make and model:
        vehicle_q = select(Vehicle).where(
            or_(
                *[
                    Vehicle.brand.ilike(f"%{v}%")
                    for v in _brand_variants(make)
                ]
            ),
            Vehicle.model.ilike(f"%{model}%"),
        )
        if year is not None:
            vehicle_q = vehicle_q.where(
                and_(
                    (Vehicle.year_from.is_(None)) | (Vehicle.year_from <= year),
                    (Vehicle.year_to.is_(None)) | (Vehicle.year_to >= year),
                )
            )
        vehicles = (await db.execute(vehicle_q)).scalars().all()
        if vehicles:
            result = await db.execute(
                select(Compatibility.product_id)
                .where(
                    Compatibility.vehicle_id.in_([v.id for v in vehicles]),
                    Compatibility.is_confirmed.is_(True),
                )
                .distinct()
            )
            product_ids = [row[0] for row in result.all()]
            if product_ids:
                compatible = True
                query = base.where(Product.id.in_(product_ids))
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
                        "confirmed_for_vehicle": True,
                    }
                    for p in products
                ]
        # Vehicle requested but no confirmed fitment (model not in DB, or no
        # verified compatibility row): do not return an empty list — show the
        # global assortment so the consultant can still sell, but explicitly
        # flag it as unverified so the LLM never claims confirmed fitment.
        query = base.order_by(Product.price).limit(limit)
        fallback = (await db.execute(query)).scalars().all()
        return [
            {
                "product_id": str(p.id),
                "sku": p.sku,
                "name": p.name,
                "category": p.category,
                "price": float(p.price) if p.price is not None else None,
                "stock_quantity": p.stock_quantity,
                "confirmed_for_vehicle": False,
            }
            for p in fallback
        ]

    query = base
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
            "confirmed_for_vehicle": False,
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
    seen: set = set()
    if vehicle_identified:
        vehicle_q = select(Vehicle).where(
            or_(
                *[
                    Vehicle.brand.ilike(f"%{v}%")
                    for v in _brand_variants(make)
                ]
            )
        )
        if model:
            vehicle_q = vehicle_q.where(Vehicle.model.ilike(f"%{model}%"))
        if year:
            vehicle_q = vehicle_q.where(
                and_(
                    (Vehicle.year_from.is_(None)) | (Vehicle.year_from <= year),
                    (Vehicle.year_to.is_(None)) | (Vehicle.year_to >= year),
                )
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
                if c.product_id in seen:
                    continue
                seen.add(c.product_id)
                product = c.product
                matches.append(
                    {
                        "product_id": str(c.product_id),
                        "product_name": product.name if product else None,
                        "type": c.type,
                        "notes": c.notes,
                        "price": float(product.price)
                        if product and product.price is not None
                        else None,
                    }
                )

    return {
        "verified": bool(matches),
        "vehicle_identified": vehicle_identified,
        "matches": matches[:5],
    }
