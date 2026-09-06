"""Import the ORIONLIGHT catalog into PostgreSQL (source of truth).

Reads catalog_orion_price_filled.csv and populates:
  shops (default shop) -> vehicles, products, compatibilities

Usage (after `docker-compose up -d` + DB tables exist):
  python ai_seller/scripts/import_catalog_db.py [--csv PATH]
"""

import argparse
import asyncio
import csv
import re
import unicodedata
from pathlib import Path
from typing import Dict, Tuple

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.infrastructure.database.session import async_session_maker, init_db
from app.infrastructure.database.models.product import (
    Compatibility,
    CompatibilityType,
    Product,
    Vehicle,
)
from app.infrastructure.database.models.shop import Shop, ShopStatus

logger = get_logger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_CSV = PROJECT_ROOT / "rag" / "knowledge" / "compatibility" / "catalog_orion_price_filled.csv"

RE_BRACKETS = re.compile(r"\[([^\]]*)\]")
RE_YEARS = re.compile(r"(\d{4})\s*[—–-]?\s*(\d{4}|н\.?\s?в\.?)")
RE_SINGLE_YEAR = re.compile(r"(\d{4})")

TRANS = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "H", "Ц": "C", "Ч": "Ch", "Ш": "Sh", "Щ": "Sch",
    "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
}


def year_range(kuzov: str) -> Tuple[int | None, int | None]:
    m = RE_BRACKETS.search(kuzov or "")
    if not m:
        return None, None
    inner = m.group(1)
    m2 = RE_YEARS.search(inner)
    if m2:
        to_raw = m2.group(2)
        return int(m2.group(1)), (int(to_raw) if to_raw and to_raw.isdigit() else None)
    m3 = RE_SINGLE_YEAR.search(inner)
    if m3:
        return int(m3.group(1)), None
    return None, None


def slugify(text: str, max_len: int = 100) -> str:
    text = "".join(TRANS.get(c, c) for c in text)
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    return text[:max_len].strip("-")


def product_sku(product_name: str) -> str:
    """Build a stable SKU from the full product name."""
    base = re.sub(r"^Светодиодные би-лед модули\s+", "", product_name).strip()
    return slugify(base)


async def load_rows(csv_path: Path) -> list:
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


async def ensure_shop(db) -> Shop:
    result = await db.execute(select(Shop).where(Shop.slug == settings.shop_id))
    shop = result.scalar_one_or_none()
    if shop is None:
        shop = Shop(
            slug=settings.shop_id,
            name="ORIONLIGHT Auto",
            status=ShopStatus.ACTIVE,
            timezone="Asia/Novosibirsk",
            default_language=settings.default_language,
        )
        db.add(shop)
        await db.flush()
    return shop


async def import_catalog(csv_path: Path) -> None:
    setup_logging()
    await init_db()

    rows = await load_rows(csv_path)
    logger.info(f"Read {len(rows)} rows from {csv_path}")

    async with async_session_maker() as db:
        shop = await ensure_shop(db)

        # Collect distinct vehicles and products first
        vehicle_keys = {}
        product_keys = {}

        for row in rows:
            brand = (row.get("marka_auto") or "").strip()
            model = (row.get("model_auto") or "").strip()
            kuzov = (row.get("kuzov_pokolenie") or "").strip()
            name = (row.get("name_model_len") or "").strip()
            price_raw = (row.get("price_model") or "").strip()
            if not name or not brand:
                continue

            if (brand, model, kuzov) not in vehicle_keys:
                y_from, y_to = year_range(kuzov)
                vehicle_keys[(brand, model, kuzov)] = {
                    "brand": brand,
                    "model": model,
                    "generation": kuzov,
                    "year_from": y_from,
                    "year_to": y_to,
                }

            if name not in product_keys:
                product_keys[name] = {
                    "price": int(price_raw) if price_raw.isdigit() else 0,
                    "sku": product_sku(name),
                }

        # Upsert vehicles
        vehicle_id_map: Dict[Tuple[str, str, str], object] = {}
        created_v = updated_v = 0
        for (brand, model, kuzov), data in vehicle_keys.items():
            result = await db.execute(
                select(Vehicle).where(
                    Vehicle.brand == brand,
                    Vehicle.model == model,
                    Vehicle.generation == kuzov,
                )
            )
            vehicle = result.scalar_one_or_none()
            if vehicle is None:
                vehicle = Vehicle(
                    brand=brand,
                    model=model,
                    generation=kuzov,
                    year_from=data["year_from"],
                    year_to=data["year_to"],
                )
                db.add(vehicle)
                await db.flush()
                created_v += 1
            else:
                updated_v += 1
            vehicle_id_map[(brand, model, kuzov)] = vehicle.id

        # Upsert products
        product_id_map: Dict[str, object] = {}
        for name, data in product_keys.items():
            result = await db.execute(
                select(Product).where(Product.shop_id == shop.id, Product.sku == data["sku"])
            )
            product = result.scalar_one_or_none()
            if product is None:
                product = Product(
                    shop_id=shop.id,
                    sku=data["sku"],
                    name=name,
                    slug=data["sku"],
                    description=name,
                    brand="ORIONLIGHT",
                    category="Би-лед модули",
                    price=data["price"],
                    currency=settings.default_currency,
                    stock_quantity=0,
                    specifications={"compatibility_source": "catalog_orion_price_filled.csv"},
                    is_active=True,
                )
                db.add(product)
                await db.flush()
            product_id_map[name] = product.id

        # Upsert compatibilities
        created_c = 0
        seen = set()
        for row in rows:
            brand = (row.get("marka_auto") or "").strip()
            model = (row.get("model_auto") or "").strip()
            kuzov = (row.get("kuzov_pokolenie") or "").strip()
            name = (row.get("name_model_len") or "").strip()
            if not name or not brand:
                continue
            vehicle_id = vehicle_id_map.get((brand, model, kuzov))
            product_id = product_id_map.get(name)
            if vehicle_id is None or product_id is None:
                continue
            key = (str(product_id), str(vehicle_id))
            if key in seen:
                continue
            seen.add(key)
            result = await db.execute(
                select(Compatibility).where(
                    Compatibility.product_id == product_id,
                    Compatibility.vehicle_id == vehicle_id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(
                    Compatibility(
                        product_id=product_id,
                        vehicle_id=vehicle_id,
                        type=CompatibilityType.DIRECT,
                        notes="Подтверждённая совместимость по каталогу ORIONLIGHT",
                        is_confirmed=True,
                    )
                )
                created_c += 1

        await db.commit()
        logger.info(
            f"Import done: vehicles created={created_v} matched={updated_v} | "
            f"products={len(product_id_map)} | compatibilities created={created_c}"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import ORIONLIGHT catalog into PostgreSQL")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    args = parser.parse_args()
    await import_catalog(Path(args.csv))


if __name__ == "__main__":
    asyncio.run(main())
