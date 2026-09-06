"""Build RAG knowledge files from the ORIONLIGHT catalog.

Reads:
  - catalog_orion_price_filled.csv  (vehicle -> compatible bi-led modules + prices)
  - product pages (html/product-*.html) with full technical characteristics

Writes into ai_seller/rag/knowledge/:
  - compatibility/vehicles.jsonl      one record per vehicle configuration
  - compatibility/modules.jsonl       unique catalog modules with prices
  - product_specs/<slug>.md           full product cards (specs + description)

Usage:
  python ai_seller/scripts/build_catalog_knowledge.py
      [--csv PATH] [--html-dir PATH] [--out PATH]

The CSV is semicolon-separated, UTF-8 (with BOM).
"""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import html as html_lib

# --- script location -----------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_CSV = PROJECT_ROOT / "rag" / "knowledge" / "compatibility" / "catalog_orion_price_filled.csv"
DEFAULT_HTML_DIR = Path("/opt/goinfre/ayeshacy/Applications/OpenCode_projects/site-biled-sales/html")
DEFAULT_OUT = PROJECT_ROOT / "rag" / "knowledge"

RE_BRACKETS = re.compile(r"\[([^\]]*)\]")
RE_YEARS = re.compile(r"(\d{4})\s*[—–-]?\s*(\d{4}|н\.?\s?в\.?)")
RE_SINGLE_YEAR = re.compile(r"(\d{4})")


def year_range(kuzov: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse a '[2006-2013]' / '[2022-н.в.]' tail into (year_from, year_to)."""
    m = RE_BRACKETS.search(kuzov or "")
    if not m:
        return None, None
    inner = m.group(1)
    m2 = RE_YEARS.search(inner)
    if m2:
        frm = int(m2.group(1))
        to_raw = m2.group(2)
        to_year = int(to_raw) if to_raw and to_raw.isdigit() else None
        return frm, to_year
    m3 = RE_SINGLE_YEAR.search(inner)
    if m3:
        y = int(m3.group(1))
        return y, None
    return None, None


def generation_label(kuzov: str) -> str:
    """Clean the generation/case label, dropping the year bracket tail."""
    return RE_BRACKETS.sub("", kuzov or "").strip().strip(",").strip()


def make_id(*parts: str) -> str:
    """Deterministic short id from parts."""
    raw = "|".join(str(p).strip() for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def translit_slug(value: str, max_len: int = 80) -> str:
    """Very small Cyrillic->latin transliteration used for filenames only."""
    mapping = {
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
    value = "".join(mapping.get(c, c) for c in value)
    value = unicodedata.normalize("NFKD", value)
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s_]+", "-", value)
    return value[:max_len].strip("-")


# --------------------------------------------------------------------------
# CSV -> vehicle compatibility
# --------------------------------------------------------------------------
def load_csv_rows(csv_path: Path) -> List[Dict[str, Any]]:
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def build_compatibility_files(
    rows: List[Dict[str, Any]], out_dir: Path
) -> Tuple[int, int, int]:
    """Build vehicles.jsonl and modules.jsonl."""
    comp_dir = out_dir / "compatibility"
    comp_dir.mkdir(parents=True, exist_ok=True)

    modules: Dict[str, Dict[str, Any]] = {}
    vehicles: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for row in rows:
        brand = (row.get("marka_auto") or "").strip()
        model = (row.get("model_auto") or "").strip()
        kuzov = (row.get("kuzov_pokolenie") or "").strip()
        name = (row.get("name_model_len") or "").strip()
        price_raw = (row.get("price_model") or "").strip().replace("\u00a0", "")
        price = int(price_raw) if price_raw.isdigit() else None

        if not name:
            continue

        key = (brand, model, kuzov)
        if key not in vehicles:
            y_from, y_to = year_range(kuzov)
            vehicles[key] = {
                "id": f"vehicle_{make_id(brand, model, kuzov)}",
                "brand": brand,
                "model": model,
                "generation_raw": kuzov,
                "generation": generation_label(kuzov),
                "year_from": y_from,
                "year_to": y_to,
                "compatible_products": [],
            }
        vehicles[key]["compatible_products"].append(
            {"name": name, "price": price}
        )

        if name not in modules:
            modules[name] = {
                "name": name,
                "price": price,
                "vehicles_count": 0,
            }
        modules[name]["vehicles_count"] += 1

    # Sort product lists for stable output
    ordered_vehicles = sorted(
        vehicles.values(), key=lambda v: (v["brand"], v["model"], v["generation_raw"])
    )
    for v in ordered_vehicles:
        seen = set()
        unique = []
        for p in v["compatible_products"]:
            if p["name"] in seen:
                continue
            seen.add(p["name"])
            unique.append(p)
        v["compatible_products"] = sorted(
            unique, key=lambda p: (p["price"] or 0, p["name"])
        )

    with open(comp_dir / "vehicles.jsonl", "w", encoding="utf-8") as f:
        for v in ordered_vehicles:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    ordered_modules = sorted(
        modules.values(), key=lambda m: (m["price"] or 0, m["name"])
    )
    with open(comp_dir / "modules.jsonl", "w", encoding="utf-8") as f:
        for m in ordered_modules:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    return len(ordered_vehicles), len(ordered_modules), len(rows)


# --------------------------------------------------------------------------
# Product pages -> product specs markdown
# --------------------------------------------------------------------------
def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_spec_table(page: str) -> List[Tuple[str, str]]:
    rows = []
    for m in re.finditer(r'<table class="specs-table">(.*?)</table>', page, re.S):
        for k, v in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td></tr>", m.group(1), re.S):
            rows.append((clean_html(k), clean_html(v)))
    return rows


def extract_product_info(page: str) -> Dict[str, Any]:
    title_m = re.search(r"<title>(.*?)</title>", page, re.S)
    title = clean_html(title_m.group(1)) if title_m else ""
    title = re.sub(r"\s*\|\s*ORIONLIGHT\s*$", "", title).strip()
    title = re.sub(r"^Купить\s+", "", title, flags=re.I).strip()

    price_m = re.search(r'"price"\s*:\s*"(\d+)"', page)
    price = int(price_m.group(1)) if price_m else None

    description = ""
    desc_m = re.search(
        r'<meta[^>]*name="description"[^>]*content="([^"]*)"', page, re.S
    )
    if desc_m:
        description = clean_html(desc_m.group(1))

    return {
        "title": title,
        "price": price,
        "description": description,
        "specs": parse_spec_table(page),
    }


def write_product_specs(html_dir: Path, out_dir: Path) -> int:
    spec_dir = out_dir / "product_specs"
    spec_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for page_file in sorted(html_dir.glob("product-*.html")):
        page = page_file.read_text(encoding="utf-8")
        info = extract_product_info(page)
        if not info["specs"] and not info["description"]:
            continue

        lines = [f"# {info['title']}"]
        if info["price"] is not None:
            lines.append(f"\n**Цена:** {info['price']} ₽")
        lines.append("**Категория:** Би-лед модули / LED оптика")
        if info["description"]:
            lines.append(f"\n## Описание\n{info['description']}")
        lines.append("\n## Характеристики\n")
        if info["specs"]:
            lines.append("| Параметр | Значение |")
            lines.append("|----------|----------|")
            for key, value in info["specs"]:
                lines.append(f"| {key} | {value} |")
        else:
            lines.append("_(характеристики на странице не заполнены)_")

        target = spec_dir / f"{page_file.stem}.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written += 1

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAG knowledge from ORIONLIGHT catalog")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--html-dir", default=str(DEFAULT_HTML_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out_dir = Path(args.out)
    csv_path = Path(args.csv)
    html_dir = Path(args.html_dir)

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    print("Reading catalog CSV ...")
    rows = load_csv_rows(csv_path)
    n_vehicles, n_modules, n_rows = build_compatibility_files(rows, out_dir)
    print(f"vehicles={n_vehicles} modules={n_modules} mapping_rows={n_rows}")
    print(f"  -> {out_dir / 'compatibility/vehicles.jsonl'}")
    print(f"  -> {out_dir / 'compatibility/modules.jsonl'}")

    if html_dir.exists():
        n_specs = write_product_specs(html_dir, out_dir)
        print(f"product specs written: {n_specs}")
        print(f"  -> {out_dir / 'product_specs'}")
    else:
        print(f"HTML dir not found, skipping product specs: {html_dir}")


if __name__ == "__main__":
    main()
