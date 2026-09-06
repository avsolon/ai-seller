"""Pure helpers to turn the knowledge base into RAG records (no qdrant deps).

Understands the layout of ai_seller/rag/knowledge:
  products/*.md            product cards (markdown)
  product_specs/*.md       detailed product specs (markdown)
  company/*.md,*.json      company info
  delivery/*.md            delivery terms
  warranty/*.md            warranty terms
  install/*.md             installation guide
  faq/*.jsonl              FAQ records
  compatibility/*.jsonl    vehicle -> compatible modules
  products.jsonl           product records (flat JSONL)
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

FOLDER_TYPE = {
    "products": "product",
    "product_specs": "product",
    "company": "company",
    "delivery": "delivery",
    "warranty": "warranty",
    "install": "manual",
    "faq": "faq",
    "compatibility": "compatibility",
}

KNOWN_JSONL = (
    "faq/products.jsonl",
    "products.jsonl",
    "compatibility/vehicles.jsonl",
    "compatibility/modules.jsonl",
)


def chunk_text(text: str, max_chars: int = 2000) -> List[str]:
    """Split text into reasonably sized, overlapping-friendly chunks."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = ""
        if len(para) > max_chars:
            for i in range(0, len(para), max_chars):
                chunks.append(para[i : i + max_chars].strip())
            continue
        current = (current + "\n\n" + para).strip()
    if current:
        chunks.append(current.strip())
    return chunks


def short_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:14]


def markdown_to_text(path: Path) -> str:
    """Read a markdown file and keep it as readable text."""
    return path.read_text(encoding="utf-8").strip()


def md_records(root: Path) -> Iterator[Dict[str, Any]]:
    """Yield records from every .md file under the knowledge root."""
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        folder = str(rel.parent).split("/")[0] if rel.parent != Path(".") else ""
        source_type = FOLDER_TYPE.get(folder, "other")
        text = markdown_to_text(path)
        if not text:
            continue
        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            yield {
                "id": f"k_{short_id(str(rel), str(idx))}",
                "title": path.stem.replace("_", " ").replace("-", " "),
                "text": chunk,
                "source_type": source_type,
                "source": str(rel),
            }


def jsonl_records(root: Path) -> Iterator[Dict[str, Any]]:
    """Yield records from known JSONL knowledge files."""
    for rel_str in KNOWN_JSONL:
        path = root / rel_str
        if not path.exists():
            continue
        if rel_str == "products.jsonl":
            source_type = "product"
        else:
            folder = rel_str.split("/")[0]
            source_type = FOLDER_TYPE.get(folder, "other")

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                text, title = _jsonl_to_text(obj)
                if not text:
                    continue
                for idx, chunk in enumerate(chunk_text(text)):
                    yield {
                        "id": f"k_{short_id(rel_str, str(line_no), str(idx))}",
                        "title": title or obj.get("name") or obj.get("id") or str(rel_str),
                        "text": chunk,
                        "source_type": source_type,
                        "source": rel_str,
                    }


def _jsonl_to_text(obj: Dict[str, Any]) -> Tuple[str, str]:
    """Convert a JSONL object to (searchable text, title)."""
    if "question" in obj and "answer" in obj:  # FAQ
        title = obj.get("question", "")
        tags = ", ".join(obj.get("tags", []))
        return f"Вопрос: {obj.get('question', '')}\nОтвет: {obj.get('answer', '')}\nТеги: {tags}", title

    if "compatible_products" in obj:  # vehicle compatibility record
        title = f"{obj.get('brand', '')} {obj.get('model', '')} {obj.get('generation_raw', '')}"
        parts = [f"Автомобиль: {obj.get('brand', '')} {obj.get('model', '')} "
                 f"{obj.get('generation_raw', '')}".strip()]
        if obj.get("year_from"):
            parts.append(f"Годы выпуска: {obj.get('year_from')}–{obj.get('year_to') or 'н.в.'}")
        products = obj.get("compatible_products", [])
        if products:
            lines = ["Совместимые би-лед модули:"]
            for p in products:
                price = p.get("price")
                lines.append(f"- {p.get('name')}" + (f" ({price} ₽)" if price else ""))
            parts.append("\n".join(lines))
        return "\n".join(parts), title

    if "vehicles_count" in obj and "name" in obj:  # module record
        name = obj.get("name", "")
        price = obj.get("price")
        line = f"Модуль: {name}" + (f"\nЦена: {price} ₽" if price else "")
        line += f"\nКоличество совместимых автомобилей: {obj.get('vehicles_count', 0)}"
        return line, name

    # generic product record
    name = obj.get("name") or obj.get("title") or ""
    if "characteristics" in obj and isinstance(obj["characteristics"], dict):
        spec_lines = [f"{k}: {v}" for k, v in obj["characteristics"].items()]
        body = "\n".join(spec_lines)
    else:
        body = obj.get("description") or obj.get("answer") or ""
    price = obj.get("price")
    price_line = f"\nЦена: {price} ₽" if price else ""
    return f"{name}{price_line}\n{body}".strip(), str(name)


def gather_records(root: Path) -> Iterator[Dict[str, Any]]:
    """Collect all knowledge records (markdown + jsonl + company json) under the root."""
    yield from md_records(root)
    yield from jsonl_records(root)

    # Company contact file (plain .json)
    contacts = root / "company" / "contacts.json"
    if contacts.exists():
        try:
            obj = json.loads(contacts.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            obj = None
        if isinstance(obj, dict):
            text = _company_to_text(obj)
            if text:
                yield {
                    "id": f"k_{short_id('company/contacts.json')}",
                    "title": "Контакты магазина",
                    "text": text,
                    "source_type": "company",
                    "source": "company/contacts.json",
                }


def _company_to_text(obj: Dict[str, Any]) -> str:
    """Render the company contact JSON as searchable text."""
    parts = [f"Компания: {obj.get('name', '')}"]
    legal = obj.get("legal_name")
    if legal:
        parts.append(f"Юридическое лицо: {legal}")
    for key in ("legal_address", "location"):
        if obj.get(key):
            parts.append(f"{key.replace('_', ' ').capitalize()}: {obj[key]}")

    contacts = obj.get("contacts")
    if isinstance(contacts, dict):
        labels = {
            "phone": "Телефон",
            "email": "Email",
            "telegram": "Telegram",
            "whatsapp": "WhatsApp",
            "youtube": "YouTube",
            "vk": "VK",
        }
        for key, label in labels.items():
            if contacts.get(key):
                parts.append(f"{label}: {contacts[key]}")

    wh = obj.get("working_hours")
    if isinstance(wh, dict):
        for title, hours in wh.items():
            if isinstance(hours, dict):
                detail = "; ".join(f"{k}: {v}" for k, v in hours.items() if v)
                if detail:
                    parts.append(f"График ({title.replace('_', ' ')}): {detail}")

    address = obj.get("address")
    if isinstance(address, dict) and address.get("office"):
        parts.append(f"Адрес офиса: {address['office']}")
    if obj.get("delivery"):
        parts.append(f"Доставка: {obj['delivery']}")
    return "\n".join(parts)


def count_records(root: Path) -> int:
    return sum(1 for _ in gather_records(root))
