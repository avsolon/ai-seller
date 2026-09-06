"""Sales taxonomy: stages, intents, emotions and types (single source of truth).

The authoritative data lives in rag/taxonomy/sales_rag_taxonomy.yaml and is loaded
at runtime; the enums here mirror that data for typed use in code.
"""

from __future__ import annotations

import enum
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

_DATA_DIR = Path(__file__).resolve().parents[3] / "rag"


class SalesStage(str, enum.Enum):
    """Stages of the sales funnel (order matters)."""

    NEW = "NEW"
    DISCOVERY = "DISCOVERY"
    NEED_IDENTIFIED = "NEED_IDENTIFIED"
    VEHICLE_QUALIFICATION = "VEHICLE_QUALIFICATION"
    PRODUCT_SELECTION = "PRODUCT_SELECTION"
    COMPARISON = "COMPARISON"
    OBJECTION = "OBJECTION"
    TRUST_BUILDING = "TRUST_BUILDING"
    PRODUCT_INFO = "PRODUCT_INFO"
    CLOSING = "CLOSING"
    ORDER = "ORDER"
    HANDOFF = "HANDOFF"
    POST_SALE = "POST_SALE"


class CustomerIntent(str, enum.Enum):
    """Customer intents from the sales taxonomy."""

    GREETING = "GREETING"
    VEHICLE_INFO = "VEHICLE_INFO"
    NEED_DISCOVERY = "NEED_DISCOVERY"
    VEHICLE_COMPATIBILITY = "VEHICLE_COMPATIBILITY"
    PRODUCT_RECOMMENDATION = "PRODUCT_RECOMMENDATION"
    PRODUCT_COMPARISON = "PRODUCT_COMPARISON"
    PRICE_QUERY = "PRICE_QUERY"
    PRICE_OBJECTION = "PRICE_OBJECTION"
    TRUST_OBJECTION = "TRUST_OBJECTION"
    DELIVERY_QUERY = "DELIVERY_QUERY"
    WARRANTY_QUERY = "WARRANTY_QUERY"
    INSTALLATION_QUERY = "INSTALLATION_QUERY"
    PURCHASE_INTENT = "PURCHASE_INTENT"
    ORDER_REQUEST = "ORDER_REQUEST"
    HESITATION = "HESITATION"
    HANDOFF_REQUEST = "HANDOFF_REQUEST"
    PRODUCT_INFO = "PRODUCT_INFO"


class CustomerEmotion(str, enum.Enum):
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    INTERESTED = "interested"
    SKEPTICAL = "skeptical"
    PRICE_SENSITIVE = "price_sensitive"
    FRUSTRATED = "frustrated"
    URGENT = "urgent"
    READY_TO_BUY = "ready_to_buy"
    CONFUSED = "confused"


class CustomerType(str, enum.Enum):
    GENERAL = "general"
    NOVICE = "novice"
    ENTHUSIAST = "enthusiast"
    PROFESSIONAL_BUYER = "professional_buyer"
    RETURNING_CUSTOMER = "returning_customer"


_FUNNEL_ORDER = [s.value for s in SalesStage]
_INTENTS = {i.value: i for i in CustomerIntent}
_EMOTIONS = {e.value: e for e in CustomerEmotion}
_TYPES = {t.value: t for t in CustomerType}


def taxonomy_path() -> Path:
    env_path = os.environ.get("SALES_RAG_TAXONOMY_PATH")
    if env_path:
        return Path(env_path)
    return _DATA_DIR / "taxonomy" / "sales_rag_taxonomy.yaml"


def taxonomy_exists() -> bool:
    return taxonomy_path().exists()


@lru_cache(maxsize=1)
def load_taxonomy() -> Dict[str, Any]:
    """Load the taxonomy YAML (cached). Returns {} if unavailable."""
    path = taxonomy_path()
    if yaml is None or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def funnel_stages() -> List[str]:
    """Ordered sales funnel as defined in the taxonomy file (fallback to enum)."""
    data = load_taxonomy()
    funnel = data.get("sales_funnel")
    if isinstance(funnel, list) and funnel:
        return [str(s) for s in funnel]
    return _FUNNEL_ORDER


def intents() -> Dict[str, str]:
    """Intent code -> description."""
    data = load_taxonomy()
    return dict(data.get("customer_intents", {}))


def emotions() -> Dict[str, str]:
    data = load_taxonomy()
    return dict(data.get("customer_emotions", {}))


def customer_types() -> Dict[str, str]:
    data = load_taxonomy()
    return dict(data.get("customer_types", {}))


def discovery_slots() -> Dict[str, Dict[str, Any]]:
    """Slot schema (required flags) from the taxonomy."""
    data = load_taxonomy()
    return dict(data.get("discovery_slots", {}))


def is_valid_stage(value: str) -> bool:
    return value in {s.value for s in SalesStage}


def is_valid_intent(value: str) -> bool:
    return value in _INTENTS


def coerce_intent(value: str) -> CustomerIntent:
    try:
        return _INTENTS[str(value)]
    except KeyError:
        return _INTENTS[str(value).upper()]


def coerce_stage(value: str) -> SalesStage:
    try:
        return SalesStage(str(value))
    except ValueError:
        return SalesStage(str(value).upper())
