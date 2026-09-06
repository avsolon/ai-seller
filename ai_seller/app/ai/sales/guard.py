"""Response Guard: lightweight rule checks before an answer is sent.

This is intentionally rule-based and conservative. It flags obvious violations
(fabricated-sounding compatibility claims, aggressive pressure, too many
questions). Fact-level grounding (price/stock) is validated by tools, not here.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.ai.sales.state import SalesState

_STRONG_COMPATIBILITY = re.compile(
    r"(точно подойд[её]т|гарантированно встанет|100% подойд[её]т|"
    r"абсолютно точно подойд|точно встанет без переделок)",
    re.IGNORECASE,
)

_AGGRESSIVE_PRESSURE = re.compile(
    r"(почему не покупаете|прямо сейчас закажите|не упустите выгоду|"
    r"скидка только сегодня|последний шанс)",
    re.IGNORECASE,
)

_FABRICATED_NUMBERS = re.compile(
    r"(гарантируем в (раз)? ?\d|свет станет в \d раза ярче)", re.IGNORECASE
)

MAX_ANSWER_LENGTH = 1200
MAX_QUESTIONS_PER_TURN = 2


class ResponseGuard:
    """Validates an agent reply before returning it to the customer."""

    def check(self, text: str, state: Optional[SalesState] = None) -> List[Dict[str, str]]:
        issues: List[Dict[str, str]] = []
        clean = (text or "").strip()

        if not clean:
            issues.append({"code": "empty_response", "detail": "Ответ пустой"})
        elif len(clean) > MAX_ANSWER_LENGTH:
            issues.append({"code": "overlong_response", "detail": "Ответ слишком длинный"})

        question_marks = clean.count("?")
        if question_marks > MAX_QUESTIONS_PER_TURN:
            issues.append(
                {"code": "too_many_questions", "detail": "Слишком много вопросов за один ход"}
            )

        if _AGGRESSIVE_PRESSURE.search(clean):
            issues.append({"code": "aggressive_pressure", "detail": "Давление на клиента"})

        if _FABRICATED_NUMBERS.search(clean):
            issues.append({"code": "fabricated_fact", "detail": "Необоснованное обещание"})

        verified = bool(state and state.vehicle.compatibility_verified)
        if not verified and _STRONG_COMPATIBILITY.search(clean):
            issues.append(
                {"code": "false_compatibility_claim", "detail": "Совместимость не подтверждена"}
            )

        return issues
