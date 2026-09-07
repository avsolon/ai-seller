"""Pure helpers for the Sales RAG dataset.

This module has no third-party dependencies so it can be imported and tested
even in minimal environments (no qdrant / no embedding models).
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def norm(value: Optional[Any]) -> Optional[str]:
    """Normalize a metadata value to lowercase for consistent Qdrant filters."""
    if value is None or value == "":
        return None
    return str(value).strip().lower()


def get_customer_type(dialogue_data: Dict[str, Any]) -> Optional[str]:
    """Extract customer type from either dataset format."""
    top_level = dialogue_data.get("customer_type")
    if top_level:
        return top_level
    return dialogue_data.get("customer_profile", {}).get("type")


def extract_dialogue_text(dialogue: List[Dict[str, Any]]) -> str:
    """Extract text from dialogue for embedding."""
    texts = []
    for message in dialogue:
        if message.get("role") == "customer":
            texts.append(f"Клиент: {message.get('text', '')}")
        elif message.get("role") == "seller":
            texts.append(f"Продавец: {message.get('text', '')}")
    return " ".join(texts)


def create_semantic_query(dialogue_data: Dict[str, Any]) -> str:
    """Create a semantic query string used for embedding a dialogue."""
    customer_type = get_customer_type(dialogue_data) or "unknown"
    scenario = dialogue_data.get("scenario", "unknown")
    intent = dialogue_data.get("intent", "unknown")
    emotion = dialogue_data.get("emotion", "neutral")
    goal = dialogue_data.get("goal", "unknown")

    query = f"Клиент типа {customer_type} находится в сценарии {scenario} "
    query += f"с намерением {intent}, эмоцией {emotion} и целью {goal}. "
    query += f"Диалог: {extract_dialogue_text(dialogue_data.get('dialogue', []))}"

    return query


def build_payload(dialogue_data: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
    """Build a Qdrant payload from a sales dialogue (supports both dataset formats)."""
    customer_type = get_customer_type(dialogue_data) or "general"

    payload: Dict[str, Any] = {
        "id": dialogue_data.get("id"),
        "scenario": norm(dialogue_data.get("scenario")) or "other",
        "customer_type": norm(customer_type) or "general",
        "sales_stage": norm(dialogue_data.get("sales_stage")) or "unknown",
        "intent": norm(dialogue_data.get("intent")) or "unknown",
        "emotion": norm(dialogue_data.get("emotion")) or "neutral",
        "goal": norm(dialogue_data.get("goal")) or "unknown",
        "label": dialogue_data.get("label", "positive"),
        "quality_score": dialogue_data.get("quality_score", 0.0),
        "language": dialogue_data.get("language", "ru"),
        "shop_id": shop_id,
        "tags": dialogue_data.get("tags", []),
        "dialogue": json.dumps(dialogue_data.get("dialogue", []), ensure_ascii=False),
        "successful_strategy": json.dumps(
            dialogue_data.get("successful_strategy", []), ensure_ascii=False
        ),
        "mistakes_to_avoid": json.dumps(
            dialogue_data.get("mistakes_to_avoid", []), ensure_ascii=False
        ),
    }

    # Only keep non-empty optional fields
    objection = dialogue_data.get("objection")
    if objection:
        payload["objection"] = norm(objection)
    if dialogue_data.get("dataset"):
        payload["dataset"] = dialogue_data["dataset"]
    if dialogue_data.get("version"):
        payload["version"] = dialogue_data["version"]

    return payload


def iter_dataset(path: Path) -> Iterator[Dict[str, Any]]:
    """Iterate over JSONL records in a file, skipping blank/invalid lines."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def validate_record(record: Dict[str, Any]) -> List[str]:
    """Return a list of problems found in a single sales record."""
    errors: List[str] = []
    if not record.get("id"):
        errors.append("missing id")
    if not record.get("scenario"):
        errors.append("missing scenario")
    if not record.get("intent"):
        errors.append("missing intent")
    if not record.get("dialogue") or not isinstance(record.get("dialogue"), list):
        errors.append("dialogue must be a non-empty list")
    elif not record["dialogue"]:
        errors.append("dialogue is empty")
    else:
        roles = {m.get("role") for m in record["dialogue"] if isinstance(m, dict)}
        if "customer" not in roles:
            errors.append("dialogue must contain a customer turn")

    label = record.get("label", "positive")
    if label not in ("positive", "negative"):
        errors.append(f"unknown label: {label}")
    quality = record.get("quality_score")
    if quality is not None and not (0.0 <= float(quality) <= 1.0):
        errors.append("quality_score out of range [0,1]")
    return errors
