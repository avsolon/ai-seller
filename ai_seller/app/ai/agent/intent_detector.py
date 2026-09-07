"""Rule-based intent detector aligned to the sales taxonomy.

Pure rules first: it is deterministic, cheap and gives the regression/eval
dataset a stable baseline. A dedicated LLM classifier can replace it later
without changing the rest of the pipeline.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.ai.sales.taxonomy import CustomerIntent

BRANDS = [
    "acura", "alfa romeo", "audi", "bmw", "cadillac", "changan", "chery",
    "chevrolet", "chrysler", "citroen", "daewoo", "dodge", "exeed", "ford",
    "geely", "haval", "honda", "hyundai", "infiniti", "jaguar", "jeep",
    "jetour", "kia", "lada", "lexus", "lifan", "mazda", "mercedes", "mini",
    "mitsubishi", "nissan", "opel", "peugeot", "porsche", "renault", "seat",
    "skoda", "subaru", "suzuki", "toyota", "volkswagen", "volvo",
    "лексус", "тойота", "хонда", "ниссан", "киа", "хендай", "бмв", "мерседес",
    "ауди", "шкода", "фольксваген", "вольво", "мазда", "субару", "лада",
]

RE_YEAR = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def _kw(text: str, words) -> bool:
    return any(w in text for w in words)


def detect(text: str) -> Optional[CustomerIntent]:
    """Return the most probable taxonomy intent for a customer message."""
    t = (text or "").lower()

    # --- high-specificity intent first --------------------------------
    if _kw(t, ("позовите человека", "человека", "менеджера", "специалист",
               "оператор", "эксперт", "передайте оператору", "нестандартн")):
        return CustomerIntent.HANDOFF_REQUEST

    if _kw(t, ("я подумаю", "подумаю", "посоветуюсь", "подумать", "дайте подумать")):
        return CustomerIntent.HESITATION

    if _kw(t, ("чем",)) and _kw(t, ("лучше", "отличается", "разница", "сравн", "vs ")):
        return CustomerIntent.PRODUCT_COMPARISON

    if _kw(t, ("дорого", "дешевле", "уложиться в", "кусается", "скидк",
               "на авито дешевле", "завышен")):
        return CustomerIntent.PRICE_OBJECTION

    if _kw(t, ("гарантируете", "гарантируешь")):
        return CustomerIntent.TRUST_OBJECTION
    if _kw(t, ("вдруг", "сгорит", "сломается", "перегорит", "не доверя",
               "точно качество", "некачествен", "насколько надежн", "про б/у")):
        return CustomerIntent.TRUST_OBJECTION
    if _kw(t, ("гарантия", "гаранти", "возврат", "обмен")):
        return CustomerIntent.WARRANTY_QUERY

    if _kw(t, ("установк", "монтаж", "сам став", "самому став", "ставлю сам",
               "буду ставить", "стану ставить", "сам установлю", "креплен",
               "переходн", "разобрать фару", "подключ", "сложно")):
        return CustomerIntent.INSTALLATION_QUERY

    if _kw(t, ("доставк", "отправ", "сегодня", "завтра", "срок", "наличи",
               "когда привез", "получ", "куда достав", "город достав", "трек",
               "есть в наличии", "нужно сегодня")):
        return CustomerIntent.DELIVERY_QUERY

    if _kw(t, ("оформить заказ", "оформляем", "оформить", "оплатить", "заказать",
               "давайте оформим", "хочу оформить")):
        return CustomerIntent.ORDER_REQUEST

    if _kw(t, ("беру", "берём", "возьму", "беру этот", "готов купить")):
        return CustomerIntent.PURCHASE_INTENT

    # --- vehicle related ----------------------------------------------
    has_brand = any(b in t for b in BRANDS)
    has_year = bool(RE_YEAR.search(t))
    if _kw(t, ("ксенон", "галоген", "оптика", "фара", "би-лед на")) or has_brand or (
        has_year and _kw(t, ("маши", "авто", "модель", "марка"))
    ):
        if _kw(t, ("подойд", "встанет", "совместим", "встанет без переделок",
                   "точно подойд")):
            return CustomerIntent.VEHICLE_COMPATIBILITY
        return CustomerIntent.VEHICLE_INFO

    if _kw(t, ("подойд", "встанет", "совместим", "совместимость", "для моей",
               "для своего авто", "какая линза подойдёт")):
        return CustomerIntent.VEHICLE_COMPATIBILITY

    # Returning customers: reference a previous conversation
    if _kw(t, ("вчера", "ранее", "снова", "уже спрашив", "помнишь", "помните",
               "я вам уже")):
        return CustomerIntent.VEHICLE_INFO

    if _kw(t, ("характеристик", "параметр", "спецификац", "технические данные",
               "без рассказов", "только данные")):
        return CustomerIntent.PRODUCT_INFO

    if _kw(t, ("посовет", "подбер", "какую выбрать", "какие линзы", "рекоменд",
               "главное", "не понимаю, какую", "не понимаю какую", "без переплат",
               "нормальн", "для дальнего", "мне нужна линза", "модель подойдет",
               "вариант под", "что взять", "что выбрать")):
        return CustomerIntent.PRODUCT_RECOMMENDATION

    if _kw(t, ("хочу", "нужно", "надо", "хотелось бы", "свет был", "яркост",
               "дальний свет", "ближний свет", "улучшить", "слабый свет",
               "ширина", "света")):
        return CustomerIntent.NEED_DISCOVERY

    if _kw(t, ("привет", "здравствуй", "добрый день", "добрый вечер", "доброе",
               "hi", "hello", "салют")):
        return CustomerIntent.GREETING

    return None


def extract_facts(text: str) -> Dict[str, object]:
    """Best-effort slot extraction (vehicle make/model/year, budget)."""
    t = (text or "").lower()
    facts: Dict[str, object] = {}

    brand = next((b for b in BRANDS if b in t), None)
    if brand:
        facts["vehicle_make"] = brand.title()
        m = re.search(rf"{re.escape(brand)}\s+([a-zа-яё0-9][\w\-]*)", t)
        if m:
            facts["vehicle_model"] = m.group(1).strip()

    year = RE_YEAR.search(t)
    if year:
        facts["vehicle_year"] = int(year.group(0))

    budget = re.search(r"(?:до|в|около|примерно)?\s*(\d{4,6})\s*(?:руб|₽|р\.?)", t)
    if budget:
        facts["budget"] = int(budget.group(1))
    else:
        budget2 = re.search(r"(?:бюджет|уложиться)\D*(\d{4,6})", t)
        if budget2:
            facts["budget"] = int(budget2.group(1))

    if _kw(t, ("ксенон",)):
        facts["headlight_type"] = "xenon"
    elif _kw(t, ("галоген",)):
        facts["headlight_type"] = "halogen"
    elif _kw(t, ("led", "светодиодн")):
        facts["headlight_type"] = "led"

    if _kw(t, ("свет был", "слабо", "ярко", "ярче", "света", "световой", " свет ", "свет")):
        if "дальний" in t:
            facts["primary_need"] = "дальний свет"
        elif "ближний" in t:
            facts["primary_need"] = "ближний свет"
        else:
            facts["primary_need"] = "лучший свет"

    return facts


def primary_objection(text: str) -> Optional[str]:
    t = (text or "").lower()
    if _kw(t, ("дорого", "дешевле", "уложиться в", "скидк", "бюджет")):
        return "PRICE"
    if _kw(t, ("качество", "не доверя", "сгорит", "вдруг", "сломается", "гарантируете")):
        return "TRUST"
    if _kw(t, ("подойд", "встанет", "совместим")):
        return "COMPATIBILITY"
    if _kw(t, ("доставк", "сегодня", "отправ", "получ")):
        return "DELIVERY"
    if _kw(t, ("гарантия", "возврат")):
        return "WARRANTY"
    if _kw(t, ("установк", "монтаж", "сам", "креплен")):
        return "INSTALLATION"
    return None
