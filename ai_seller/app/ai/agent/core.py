"""SellerAgent Core v1 — deterministic sales controller.

The controller owns business logic (what stage, which slots, which tools, how to
answer); the LLM is only used for NLU (analyze_intent fallback) and response
generation. RAG/GigaChat/Ollama plug in as adapters without changing this core.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.decision import AgentDecision
from app.ai.agent.intent_detector import detect, extract_facts, primary_objection
from app.ai.sales import (
    SalesState,
    SalesStateService,
    determine_next_stage,
    missing_slots,
)
from app.ai.sales.guard import ResponseGuard
from app.ai.sales.taxonomy import CustomerIntent, SalesStage
from app.core.logging import get_logger
from app.infrastructure.database.models.agent_run import AgentRun
from app.infrastructure.database.models.conversation import Conversation

logger = get_logger(__name__)

FALLBACK_ACK = "Спасибо за сообщение! Я передал ваш вопрос. Менеджер свяжется с вами в ближайшее время."
GENERATION_TIMEOUT = 8.0

STRATEGY_BY_INTENT: Dict[str, str] = {
    "GREETING": "greet_and_qualify",
    "VEHICLE_INFO": "collect_vehicle",
    "NEED_DISCOVERY": "discover_need",
    "VEHICLE_COMPATIBILITY": "verify_compatibility",
    "PRODUCT_RECOMMENDATION": "recommend",
    "PRODUCT_COMPARISON": "compare",
    "PRICE_QUERY": "answer_price",
    "PRICE_OBJECTION": "handle_price_objection",
    "TRUST_OBJECTION": "build_trust",
    "DELIVERY_QUERY": "answer_delivery",
    "WARRANTY_QUERY": "answer_warranty",
    "INSTALLATION_QUERY": "guide_installation",
    "PURCHASE_INTENT": "close",
    "ORDER_REQUEST": "create_order",
    "HESITATION": "reduce_hesitation",
    "HANDOFF_REQUEST": "handoff",
    "PRODUCT_INFO": "answer_product_info",
}

STRATEGY_BY_STAGE: Dict[str, str] = {
    "NEW": "qualify_start",
    "DISCOVERY": "collect_vehicle_and_need",
    "VEHICLE_QUALIFICATION": "verify_compatibility",
    "OBJECTION": "handle_objection",
    "CLOSING": "close",
    "ORDER": "process_order",
    "HANDOFF": "handoff",
}


class SellerAgentCore:
    """Sales controller: process_message orchestrates the whole pipeline."""

    def __init__(
        self,
        cache: Optional[Any] = None,
        guard: Optional[ResponseGuard] = None,
    ) -> None:
        self.cache = cache
        self.guard = guard or ResponseGuard()

    # --- public pipeline ---------------------------------------------------
    async def process_message(
        self,
        db: AsyncSession,
        conversation: Conversation,
        text: str,
        products: Optional[List[Any]] = None,
        allow_llm: bool = True,
    ) -> Dict[str, Any]:
        state = await self.load_sales_state(db, conversation.id)
        state_before = state.to_dict()

        intent, facts = await self.analyze_intent(text, state)
        state = await self.update_sales_state(state, intent, facts, text)
        decision = await self.decide_action(state, intent)

        patterns, knowledge = await self.retrieve_sales_knowledge(decision, text)
        tools_facts = await self.call_tools(db, decision, state, products or [])

        reply, generation = await self.generate_response(
            decision, text, state, patterns, knowledge, tools_facts,
            products or [], allow_llm,
        )
        issues = self.validate_response(reply, state)

        await self.persist_result(
            db, conversation, state, decision, reply, state_before, generation
        )

        if state.handoff_requested:
            conversation.status = "handed_off"

        return {
            "reply": reply,
            "decision": decision.to_dict(),
            "intent": decision.intent.value if decision.intent else None,
            "stage": state.stage.value,
            "handoff": state.handoff_requested,
            "guard_issues": issues,
            "tools": tools_facts,
            "state": state,
        }

    # --- pipeline stages ---------------------------------------------------
    async def load_conversation(
        self, db: AsyncSession, conversation_id: UUID
    ) -> Conversation:
        conversation = await db.get(Conversation, conversation_id)
        return conversation  # type: ignore[return-value]

    async def load_sales_state(self, db: AsyncSession, conversation_id: UUID) -> SalesState:
        service = SalesStateService(db, cache=self.cache)
        return await service.load(conversation_id)

    async def analyze_intent(
        self, text: str, state: SalesState
    ) -> Tuple[Optional[CustomerIntent], Dict[str, object]]:
        intent = detect(text)
        facts = extract_facts(text)
        if intent == CustomerIntent.INSTALLATION_QUERY and "сам" in (text or "").lower():
            facts["installation_mode"] = "self"
        return intent, facts

    async def update_sales_state(
        self,
        state: SalesState,
        intent: Optional[CustomerIntent],
        facts: Dict[str, object],
        text: str,
    ) -> SalesState:
        make = facts.get("vehicle_make")
        if make:
            state.vehicle.make = str(make)
        model = facts.get("vehicle_model")
        if model:
            state.vehicle.model = str(model)
        year = facts.get("vehicle_year")
        if year:
            state.vehicle.year = int(year)
        if facts.get("headlight_type"):
            state.vehicle.headlight_type = str(facts["headlight_type"])
        if facts.get("budget"):
            state.need.budget = facts["budget"]  # type: ignore[assignment]
        if facts.get("primary_need"):
            state.need.primary_need = str(facts["primary_need"])
        if facts.get("installation_mode"):
            state.purchase.installation_mode = str(facts["installation_mode"])

        state.intent = intent
        state.last_customer_message = text

        if intent == CustomerIntent.HANDOFF_REQUEST:
            state.handoff_requested = True
        elif intent in (
            CustomerIntent.PRICE_OBJECTION,
            CustomerIntent.TRUST_OBJECTION,
            CustomerIntent.PRICE_QUERY,
        ):
            state.add_objection(primary_objection(text) or "PRICE", text)
        elif intent == CustomerIntent.PURCHASE_INTENT:
            state.purchase.ready_to_buy = True
        elif intent == CustomerIntent.ORDER_REQUEST:
            state.purchase.order_created = True
        elif intent == CustomerIntent.HESITATION:
            state.add_objection("HESITATION", text)
        return state

    async def decide_action(
        self, state: SalesState, intent: Optional[CustomerIntent]
    ) -> AgentDecision:
        next_stage = determine_next_stage(state)
        state.stage = next_stage
        state.missing_slots = missing_slots(state)

        routed = _route_tools(intent)
        strategy = STRATEGY_BY_INTENT.get(
            intent.value if intent else "", STRATEGY_BY_STAGE.get(state.stage.value, "general")
        )

        return AgentDecision(
            intent=intent,
            stage=state.stage,
            next_stage=next_stage,
            required_slots=list(state.missing_slots),
            tool_calls=routed,
            rag_query=_build_rag_query(state, intent),
            response_strategy=strategy,
            handoff=bool(state.handoff_requested),
            confidence=0.9 if intent is not None else 0.3,
        )

    async def retrieve_sales_knowledge(
        self, decision: AgentDecision, text: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        patterns: List[Dict[str, Any]] = []
        knowledge: List[Dict[str, Any]] = []
        try:
            from app.ai.rag.retriever import RAGRetriever

            retriever = RAGRetriever()
            if decision.rag_query or decision.intent is not None:
                patterns = await retriever.search_sales_dialogues(
                    query=text,
                    intent=decision.intent.value if decision.intent else None,
                    sales_state=decision.stage.value,
                    limit=3,
                )
            if decision.intent in (
                CustomerIntent.DELIVERY_QUERY,
                CustomerIntent.WARRANTY_QUERY,
                CustomerIntent.INSTALLATION_QUERY,
                CustomerIntent.TRUST_OBJECTION,
                CustomerIntent.PRODUCT_INFO,
            ):
                knowledge = await retriever.search_knowledge(query=text, limit=3)
        except Exception as e:
            logger.warning(f"RAG unavailable: {e}")
        return patterns, knowledge

    async def call_tools(
        self,
        db: AsyncSession,
        decision: AgentDecision,
        state: SalesState,
        products: List[Any],
    ) -> List[Dict[str, Any]]:
        """Deterministic tool calls over the catalog/products passed in."""
        results: List[Dict[str, Any]] = []
        wanted = decision.tool_calls

        if not products and ("search_products" in wanted or "get_price" in wanted):
            from sqlalchemy import select

            from app.infrastructure.database.models.product import Product

            result = await db.execute(
                select(Product).where(Product.is_active.is_(True))
            )
            products = list(result.scalars().all())

        if "search_products" in wanted or decision.intent == CustomerIntent.PRODUCT_RECOMMENDATION:
            shown = sorted(products, key=lambda p: float(p.price))[:3]
            results.append(
                {
                    "tool": "search_products",
                    "result": [
                        {
                            "name": p.name,
                            "price": float(p.price),
                            "stock": p.stock_quantity,
                            "category": p.category,
                        }
                        for p in shown
                    ],
                }
            )

        if "get_price" in wanted or decision.intent == CustomerIntent.PRICE_QUERY:
            if state.selected_product is not None:
                match = next(
                    (p for p in products if p.id == _as_uuid(state.selected_product.product_id)),
                    None,
                )
                if match is not None:
                    results.append(
                        {"tool": "get_price", "result": {"name": match.name, "price": float(match.price)}}
                    )

        if "get_stock" in wanted and products:
            shown = sorted(products, key=lambda p: float(p.price))[:3]
            results.append(
                {
                    "tool": "get_stock",
                    "result": [
                        {"name": p.name, "stock_quantity": p.stock_quantity} for p in shown
                    ],
                }
            )

        if "check_compatibility" in wanted:
            results.append(
                {
                    "tool": "check_compatibility",
                    "result": {
                        "verified": state.vehicle.compatibility_verified,
                        "vehicle": state.vehicle.is_identified,
                    },
                }
            )
        return results

    async def generate_response(
        self,
        decision: AgentDecision,
        text: str,
        state: SalesState,
        patterns: List[Dict[str, Any]],
        knowledge: List[Dict[str, Any]],
        tools_facts: List[Dict[str, Any]],
        products: List[Any],
        allow_llm: bool,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        prompt = _build_prompt(decision, text, state, patterns, knowledge, tools_facts, products)
        generation = None
        if allow_llm:
            generation = await self._call_llm(prompt)
        if generation is not None and generation["text"]:
            return generation["text"], generation

        from app.ai.sales.transitions import next_question

        question = next_question(state) if state.missing_slots else None
        return question or FALLBACK_ACK, None

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
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
            logger.warning(f"LLM unavailable: {e}")
            return None

    def validate_response(self, reply: str, state: SalesState) -> List[Dict[str, str]]:
        issues = self.guard.check(reply, state)
        if issues:
            logger.warning(f"Response guard issues: {issues}")
        return issues

    async def persist_result(
        self,
        db: AsyncSession,
        conversation: Conversation,
        state: SalesState,
        decision: AgentDecision,
        reply: str,
        state_before: Dict[str, Any],
        generation: Optional[Dict[str, Any]],
    ) -> None:
        service = SalesStateService(db, cache=self.cache)
        await service.save(state, reason=decision.intent.value if decision.intent else "message")

        provider = (generation or {}).get("provider", "rule_fallback")
        model = (generation or {}).get("model", "fallback")
        latency_ms = (generation or {}).get("latency_ms", 0)

        db.add(
            AgentRun(
                conversation_id=conversation.id,
                model_provider=provider,
                model_name=model,
                prompt_version="seller-v1",
                state_before=state_before,
                state_after=state.to_dict(),
                response=reply,
                latency_ms=latency_ms,
            )
        )
        await db.flush()


# --- pure helpers ----------------------------------------------------------


def _as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _route_tools(intent: Optional[CustomerIntent]) -> List[str]:
    mapping = {
        CustomerIntent.VEHICLE_COMPATIBILITY: ["check_compatibility"],
        CustomerIntent.PRODUCT_RECOMMENDATION: ["search_products", "get_price"],
        CustomerIntent.PRODUCT_COMPARISON: ["search_products", "get_price"],
        CustomerIntent.PRICE_QUERY: ["get_price"],
        CustomerIntent.PRICE_OBJECTION: ["get_price"],
        CustomerIntent.PURCHASE_INTENT: ["search_products"],
        CustomerIntent.ORDER_REQUEST: [],
    }
    return mapping.get(intent, [])  # type: ignore[arg-type]


def _build_rag_query(state: SalesState, intent: Optional[CustomerIntent]) -> str:
    parts = [
        f"intent={intent.value if intent else 'general'}",
        f"stage={state.stage.value}",
    ]
    if state.vehicle.is_identified:
        parts.append(
            f"vehicle={state.vehicle.make} {state.vehicle.model} {state.vehicle.year}"
        )
    if state.need.primary_need:
        parts.append(f"need={state.need.primary_need}")
    if state.need.budget is not None:
        parts.append(f"budget={state.need.budget}")
    return "; ".join(parts)


def _build_prompt(
    decision: AgentDecision,
    text: str,
    state: SalesState,
    patterns: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    tools_facts: List[Dict[str, Any]],
    products: List[Any],
) -> str:
    known = []
    if state.vehicle.is_identified:
        known.append(f"Автомобиль: {state.vehicle.make} {state.vehicle.model} ({state.vehicle.year})")
    if state.vehicle.headlight_type:
        known.append(f"Тип оптики: {state.vehicle.headlight_type}")
    if state.need.primary_need:
        known.append(f"Потребность: {state.need.primary_need}")
    if state.need.budget is not None:
        known.append(f"Бюджет: {state.need.budget} ₽")

    patterns_lines = []
    for p in patterns[:2]:
        dialogue = p.get("dialogue")
        if isinstance(dialogue, str):
            try:
                dialogue = json.loads(dialogue)
            except (ValueError, TypeError):
                dialogue = None
        if isinstance(dialogue, list):
            snippet = " ".join(f"{m.get('role')}: {m.get('text', '')}" for m in dialogue[:4])
            patterns_lines.append(snippet[:500])
    patterns_block = "\n".join(f"- {s}" for s in patterns_lines)

    facts_block = "\n".join(
        f"- {k.get('content') or k.get('text', '')}" for k in knowledge[:2]
    )

    tools_lines = []
    for call in tools_facts:
        tools_lines.append(f"{call['tool']}: {json.dumps(call['result'], ensure_ascii=False)}")
    tools_block = "\n".join(tools_lines)

    products_block = "\n".join(
        f"- {p.name} — {float(p.price)} ₽ (в наличии {p.stock_quantity})"
        for p in products[:3]
    )

    return f"""Ты — продавец-консультант светодиодных линз и би-лед модулей.

Правила:
- Отвечай коротко (1-3 предложения), на русском.
- НЕ выдумывай цену, наличие, характеристики или совместимость.
- Если данных недостаточно — задай ОДИН уточняющий вопрос.
- Не копируй паттерны дословно — перенимай подход.

Намерение: {decision.intent.value if decision.intent else 'general'}
Этап: {decision.stage.value} (стратегия: {decision.response_strategy})

Известно о клиенте:
{chr(10).join(known) if known else '- ничего'}

Поведенческие паттерны (Sales RAG):
{patterns_block or '- нет'}

Факты (Knowledge RAG, используй только их):
{facts_block or '- нет'}

Проверенные данные инструментов (цены/наличие):
{tools_block or '- нет'}

Доступные товары:
{products_block or '- нет'}

Сообщение клиента: {text}"""
