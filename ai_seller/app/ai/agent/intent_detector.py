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

    if _kw(t, ("чем",)) and _kw(t, ("лучше", "отличается", "отличают", "отличие",
                                    "разница", "разниц", "сравн", "vs ", "или что")):
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

    if _kw(t, ("доставк", "отправ", "сегодня", "завтра", "срок", "когда привез",
               "когда приед", "получ", "куда достав", "город достав", "трек",
               "нужно сегодня")):
        return CustomerIntent.DELIVERY_QUERY

    if _kw(t, ("оформить заказ", "оформляем", "оформить", "оплатить", "заказать",
               "давайте оформим", "хочу оформить")):
        return CustomerIntent.ORDER_REQUEST

    if _kw(t, ("беру", "берём", "возьму", "беру этот", "готов купить")):
        return CustomerIntent.PURCHASE_INTENT

    if _kw(t, ("сколько сто", "стоимост", "цена", "цену", "по цене", "прайс",
               "почем", "за сколько", "ценник", "по деньгам", "с ценой")):
        return CustomerIntent.PRICE_QUERY

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
               "вариант под", "что взять", "что выбрать", "ассортимент",
               "какие есть", "что есть", "какие у вас есть", "что у вас есть",
               "что в наличии", "в наличии", "наличие", "наличи", "из наличия",
               "предлож", "что предложите", "что можешь предложить",
               "подбери", "подобрать", "покажи", "какие модели", "какие варианты",
               "несколько вариантов", "модель для моего", "модель для моей",
               "подскажи какие", "перечисли", "каталог", "линейка",
               "что можете предложить", "что подойдет для моего")):
        return CustomerIntent.PRODUCT_RECOMMENDATION

    if _kw(t, ("нептун", "neptun", "плутон", "pluton", "space ship",
               "спейс шип", "криптон", "krypton", "орион", "orion",
               "orionlight", "вега", "vega", "a14", "a16", "a22", "a7", "a9")):
        return CustomerIntent.PRODUCT_RECOMMENDATION

    if _kw(t, ("привет", "здравствуй", "добрый день", "добрый вечер", "доброе",
               "hi", "hello", "салют")):
        return CustomerIntent.GREETING

    if _kw(t, ("хочу", "нужн", "надо", "хотелось бы", "свет был", "яркост",
               "дальний свет", "ближний свет", "улучшить", "слабый свет",
               "ширина", "ширин", "дальност", "света", "все сразу", "ярче")):
        return CustomerIntent.NEED_DISCOVERY

    return None


def extract_facts(text: str) -> Dict[str, object]:
    """Best-effort slot extraction (vehicle make/model/year, budget)."""
    t = (text or "").lower()
    facts: Dict[str, object] = {}

    brand = next((b for b in BRANDS if b in t), None)
    if brand:
        facts["vehicle_make"] = brand.title()
        m = re.search(rf"{re.escape(brand)}\s+([a-zа-яё0-9][\w\-]*)", t)
        if m and m.group(1) not in {
            "подойд", "подойдут", "подходит", "нужн", "модули", "линз",
            "сколько", "цена", "стоит", "есть", "для", "дай", "хочу",
            "встанет", "сравнить",
        }:
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

    if _kw(t, ("не родн", "не штатн", "не заводск", "не оригинал")):
        facts["current_lens"] = "aftermarket"
    elif _kw(t, ("штатн", "родн", "заводск", "не менял", "не убирал",
                 "ничего не менял", "как с завода", "с завода")):
        facts["current_lens"] = "factory"
    elif not _kw(t, ("хочу", "хотел", "хотелось", "заменить", "заменю",
                     "поставить", "установить", "поставлю", "планир")):
        if _kw(t, ("менял", "меняли", "переделан", "переделывал", "колхоз",
                   "уже би", "стоят би", "би-лед", "билед",
                   "после установки", "тюнинг")):
            facts["current_lens"] = "aftermarket"

    if _kw(t, ("все сразу", "всё сразу", "и то и то", "и то и другое",
               "все вместе", "все хочу", "все опции", "по максимуму")):
        facts["primary_need"] = "все сразу"
    else:
        need_terms = []
        if "дальний" in t or _kw(t, ("дальност", "дальне", "дальн", "далеко")):
            need_terms.append("дальний свет")
        if "ближний" in t:
            need_terms.append("ближний свет")
        if _kw(t, ("ширин", "шире", "широк", "угол")):
            need_terms.append("ширина света")
        if _kw(t, ("яркост", "ярче", "ярко", "ярк")):
            need_terms.append("яркость")
        if need_terms:
            facts["primary_need"] = " и ".join(need_terms) if len(need_terms) > 1 else need_terms[0]
        elif _kw(t, ("свет", "слабо", "световой", "освещени", "светит",
                     "плохо светил", "светил слабо")):
            facts["primary_need"] = "лучший свет"

    return facts


_ORDINAL_VARIANT_RE = re.compile(
    r"(?:перв|втор|трет|четверт|пят|шест)\w*"
    r"\s+(?:вариант|модул|модел|товар|комплект|позици|опци)\w*"
)
_THIS_VARIANT_RE = re.compile(
    r"(?:этот|эту|эта|эти|данн)\w*\s+(?:вариант|модул|модел|товар|комплект|линз|оптик)\w*"
)
_MODEL_TOKEN_RE = re.compile(
    r"(?:neptun|нептун|pluton|плутон|vega|вега|krypton|криптон|space\s?ship|"
    r"спейс\s?шип|orion\w*|орион\w*|a14|a16|a22|a7|a9)"
)
_PICK_VERB_RE = re.compile(r"(?:выбираю|выберу|выбрал\w*|остановлюсь|понравил\w*|нравится)")
_QUESTION_HINT_RE = re.compile(
    r"(?:сколько|цена|ценн|прайс|почем|стоит|стоимость|дорог|дешевле|"
    r"подойд\w*|встанет|совместим\w*|можно|подробнее|какой|какая|какие|"
    r"какое|отзыв|гарант\w*|достав\w*|оформ\w*|оплат\w*|отлич\w*|сравн\w*|"
    r"разниц\w*)"
)


def is_purchase_selection(text: str) -> bool:
    """True when the client is picking one of the offered options.

    Conservative and used only as an upgrade inside core.analyze_intent for
    intents that are still generic (None / recommendation / product info).
    Question, price and comparison phrasing is deliberately excluded.
    """
    t = (text or "").lower()
    if not t or _QUESTION_HINT_RE.search(t):
        return False
    if _ORDINAL_VARIANT_RE.search(t) or _THIS_VARIANT_RE.search(t):
        return True
    return bool(_PICK_VERB_RE.search(t) and _MODEL_TOKEN_RE.search(t))


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
