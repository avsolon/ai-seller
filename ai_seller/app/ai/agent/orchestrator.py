"""SellerAgent orchestrator: ties intent detection, SalesState and reply generation.

Flow (per doc 8/9 use case):
  message -> intent -> SalesState update -> transition -> reply (LLM w/ fallback)
         -> response guard -> save state -> AgentRun
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.intent_detector import detect, extract_facts, primary_objection
from app.ai.sales import (
    SalesState,
    SalesStateService,
    determine_next_stage,
    missing_slots,
    next_question,
)
from app.ai.sales.guard import ResponseGuard
from app.ai.sales.taxonomy import CustomerIntent, SalesStage
from app.core.logging import get_logger
from app.infrastructure.database.models.agent_run import AgentRun
from app.infrastructure.database.models.conversation import Conversation

logger = get_logger(__name__)

FALLBACK_ACK = "Спасибо за сообщение! Я передал ваш вопрос. Менеджер свяжется с вами в ближайшее время."
GENERATION_TIMEOUT = 8.0  # seconds


async def _retrieve_sales_patterns(
    text: str, intent: Optional[CustomerIntent], stage: SalesStage
) -> List[Dict[str, Any]]:
    try:
        from app.ai.rag.retriever import RAGRetriever

        retriever = RAGRetriever()
        return await retriever.search_sales_dialogues(
            query=text,
            intent=intent.value if intent else None,
            sales_state=stage.value,
            limit=3,
        )
    except Exception as e:
        logger.warning(f"Sales RAG unavailable: {e}")
        return []


async def _retrieve_knowledge(text: str) -> List[Dict[str, Any]]:
    try:
        from app.ai.rag.retriever import RAGRetriever

        retriever = RAGRetriever()
        return await retriever.search_knowledge(query=text, limit=3)
    except Exception as e:
        logger.warning(f"Knowledge RAG unavailable: {e}")
        return []


def _apply_facts(state: SalesState, facts: Dict[str, object]) -> None:
    make = facts.get("vehicle_make")
    if make:
        state.vehicle.make = str(make)
    model = facts.get("vehicle_model")
    if model:
        state.vehicle.model = str(model)
    year = facts.get("vehicle_year")
    if year:
        state.vehicle.year = int(year)
    headlight = facts.get("headlight_type")
    if headlight:
        state.vehicle.headlight_type = str(headlight)
    budget = facts.get("budget")
    if budget:
        state.need.budget = budget  # type: ignore[assignment]
    need = facts.get("primary_need")
    if need:
        state.need.primary_need = str(need)
    mode = facts.get("installation_mode")
    if mode:
        state.purchase.installation_mode = str(mode)


def _update_from_intent(state: SalesState, intent: Optional[CustomerIntent], text: str) -> None:
    if intent is None:
        return
    if intent == CustomerIntent.HANDOFF_REQUEST:
        state.handoff_requested = True
    elif intent in (CustomerIntent.PRICE_OBJECTION, CustomerIntent.TRUST_OBJECTION,
                    CustomerIntent.PRICE_QUERY):
        code = primary_objection(text) or "PRICE"
        state.add_objection(code, text)
    elif intent == CustomerIntent.PURCHASE_INTENT:
        state.purchase.ready_to_buy = True
    elif intent == CustomerIntent.ORDER_REQUEST:
        state.purchase.order_created = True
    elif intent == CustomerIntent.HESITATION:
        state.add_objection("HESITATION", text)


def _build_prompt(
    text: str,
    intent: Optional[CustomerIntent],
    state: SalesState,
    sales_patterns: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    products: List[Any],
) -> str:
    known = []
    if state.vehicle.is_identified:
        known.append(
            f"Автомобиль: {state.vehicle.make} {state.vehicle.model} ({state.vehicle.year})"
        )
    if state.vehicle.headlight_type:
        known.append(f"Тип оптики: {state.vehicle.headlight_type}")
    if state.need.primary_need:
        known.append(f"Потребность: {state.need.primary_need}")
    if state.need.budget is not None:
        known.append(f"Бюджет: {state.need.budget} ₽")
    if state.selected_product is not None and state.selected_product.name:
        known.append(f"Выбранный товар: {state.selected_product.name}")

    patterns_text = []
    for p in sales_patterns[:2]:
        import json

        dialogue = p.get("dialogue")
        if isinstance(dialogue, str):
            try:
                dialogue = json.loads(dialogue)
            except (ValueError, TypeError):
                dialogue = None
        if isinstance(dialogue, list):
            snippet = " ".join(
                f"{m.get('role')}: {m.get('text', '')}" for m in dialogue[:4]
            )
            patterns_text.append(snippet[:500])
    patterns_block = "\n".join(f"- {s}" for s in patterns_text)

    facts_block = "\n".join(f"- {k.get('content') or k.get('text', '')}" for k in knowledge[:2])
    products_block = "\n".join(
        f"- {p.name} — {float(p.price)} ₽" for p in (products or [])[:3]
    )

    return f"""Ты — продавец-консультант светодиодных линз и би-лед модулей.

Правила:
- Отвечай коротко (1-3 предложения), на русском.
- НЕ выдумывай цену, наличие, характеристики или совместимость.
- Если данных недостаточно — задай ОДИН уточняющий вопрос.
- Не копируй паттерны дословно — перенимай подход.

Намерение клиента: {intent.value if intent else 'general'}
Этап продажи: {state.stage.value}
Известно о клиенте:
{chr(10).join(known) if known else '- ничего'}

Поведенческие паттерны (Sales RAG):
{patterns_block or '- нет'}

Факты (Knowledge RAG, используй только их):
{facts_block or '- нет'}

Доступные товары (только проверенные цена/наличие):
{products_block or '- нет'}

Сообщение клиента: {text}"""


async def _generate_reply(
    prompt: str,
) -> Optional[Dict[str, Any]]:
    """Call the LLM gateway; returns None when unavailable or too slow."""
    try:
        from app.ai.llm.manager import LLMManager

        manager = LLMManager()
        start = time.monotonic()
        response = await asyncio.wait_for(
            manager.generate(prompt=prompt, temperature=0.4, max_tokens=700),
            timeout=GENERATION_TIMEOUT,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "text": response.text.strip(),
            "provider": response.provider,
            "model": response.model,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        logger.warning(f"LLM generation unavailable: {e}")
        return None


async def process_message(
    db: AsyncSession,
    conversation: Conversation,
    text: str,
    products: Optional[List[Any]] = None,
    allow_llm: bool = True,
) -> Dict[str, Any]:
    """Process a customer message end-to-end and persist state + agent run."""
    intent = detect(text)
    facts = extract_facts(text)
    if intent == CustomerIntent.INSTALLATION_QUERY and "сам" in text.lower():
        facts["installation_mode"] = "self"

    service = SalesStateService(db)
    state = await service.load(conversation.id)
    state_before = state.to_dict()

    state.intent = intent
    state.last_customer_message = text
    _apply_facts(state, facts)
    _update_from_intent(state, intent, text)

    # Resolve and record the target stage
    state.stage = determine_next_stage(state)
    state.missing_slots = missing_slots(state)

    # Prepare context + reply
    sales_patterns = await _retrieve_sales_patterns(text, intent, state.stage)
    knowledge = await _retrieve_knowledge(text)
    prompt = _build_prompt(text, intent, state, sales_patterns, knowledge, products or [])
    generation = await _generate_reply(prompt) if allow_llm else None

    if generation is not None and generation["text"]:
        reply = generation["text"]
        provider = generation["provider"]
        model = generation["model"]
        latency_ms = generation["latency_ms"]
    else:
        candidate = next_question(state) if state.missing_slots else None
        reply = candidate or FALLBACK_ACK
        provider = "rule_fallback"
        model = "fallback"
        latency_ms = 0

    issues = ResponseGuard().check(reply, state)
    if issues:
        logger.warning(f"Response guard issues: {issues}")

    # Persist state (cache + sales_states + conversation + transitions)
    await service.save(state, reason=intent.value if intent else "message")

    # Audit run
    run = AgentRun(
        conversation_id=conversation.id,
        model_provider=provider,
        model_name=model,
        prompt_version="seller-v1",
        state_before=state_before,
        state_after=state.to_dict(),
        retrieved_chunks=[str(p.get("id")) for p in sales_patterns[:5]],
        response=reply,
        latency_ms=latency_ms,
    )
    db.add(run)
    await db.flush()

    if state.handoff_requested:
        conversation.status = "handed_off"

    return {
        "reply": reply,
        "intent": intent.value if intent else None,
        "stage": state.stage.value,
        "handoff": state.handoff_requested,
        "guard_issues": issues,
        "state": state,
    }
