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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.decision import AgentDecision
from app.ai.agent.intent_detector import (
    detect,
    extract_facts,
    is_purchase_selection,
    primary_objection,
)
from app.ai.sales import (
    SalesState,
    SalesStateService,
    determine_next_stage,
    missing_slots,
)
from app.ai.sales.guard import ResponseGuard
from app.ai.sales.taxonomy import CustomerIntent, SalesStage
from app.ai.tools import ToolContext, build_default_registry
from app.core.logging import get_logger
from app.infrastructure.database.models.agent_run import AgentRun, ToolCall
from app.infrastructure.database.models.conversation import Conversation, Message

logger = get_logger(__name__)

FALLBACK_ACK = "Спасибо за сообщение! Я передал ваш вопрос. Менеджер свяжется с вами в ближайшее время."
GENERATION_TIMEOUT = 120.0

# Doc 10 policy: only these intents need full Sales RAG retrieval.
RAG_REQUIRED_INTENTS = {
    "PRODUCT_RECOMMENDATION",
    "PRODUCT_COMPARISON",
    "PRICE_OBJECTION",
    "TRUST_OBJECTION",
    "HESITATION",
    "PURCHASE_INTENT",
}

# Knowledge RAG is useful for factual policy intents.
RAG_KNOWLEDGE_INTENTS = {
    "DELIVERY_QUERY",
    "WARRANTY_QUERY",
    "INSTALLATION_QUERY",
    "TRUST_OBJECTION",
    "PRODUCT_INFO",
}

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
        llm_gateway: Optional[Any] = None,
        retriever: Optional[Any] = None,
        tools: Optional[Any] = None,
    ) -> None:
        self.cache = cache
        self.guard = guard or ResponseGuard()
        # Pluggable adapters; when None the real GigaChat/Ollama and Qdrant
        # adapters are created lazily (and degrade gracefully when unavailable).
        self._llm_gateway = llm_gateway
        self._retriever = retriever
        self._tools = tools

    def _registry(self):
        if self._tools is None:
            self._tools = build_default_registry()
        return self._tools

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
        tools_facts = await self.call_tools(db, conversation, decision, state, products or [])

        history_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(6)
        )
        history_messages = list(reversed(history_result.scalars().all()))

        reply, generation = await self.generate_response(
            decision, text, state, patterns, knowledge, tools_facts,
            products or [], allow_llm, history_messages,
        )
        issues = self.validate_response(reply, state)

        await self.persist_result(
            db, conversation, state, decision, reply, state_before, generation,
            tools=tools_facts,
            retrieved=[p.get("id") for p in patterns],
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
        if (
            intent is None
            and facts.get("vehicle_year") is not None
            and state.vehicle.make
            and state.vehicle.model
            and not state.vehicle.year
        ):
            intent = CustomerIntent.PRODUCT_RECOMMENDATION
        if (
            intent in (
                None,
                CustomerIntent.PRODUCT_RECOMMENDATION,
                CustomerIntent.PRODUCT_INFO,
            )
            and is_purchase_selection(text)
        ):
            intent = CustomerIntent.PURCHASE_INTENT
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
        if facts.get("current_lens"):
            state.vehicle.current_lens = str(facts["current_lens"])
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

        intent = decision.intent
        need_sales = intent is not None and intent.value in RAG_REQUIRED_INTENTS
        need_knowledge = intent is not None and intent.value in RAG_KNOWLEDGE_INTENTS
        if not need_sales and not need_knowledge:
            return patterns, knowledge

        try:
            if self._retriever is not None:
                retriever = self._retriever
            else:
                from app.ai.rag.retriever import RAGRetriever

                retriever = RAGRetriever()
            if need_sales:
                patterns = await retriever.search_sales_dialogues(
                    query=decision.rag_query or text,
                    intent=intent.value,
                    sales_state=decision.stage.value,
                    limit=3,
                )
            if need_knowledge:
                knowledge = await retriever.search_knowledge(query=text, limit=3)
        except Exception as e:
            logger.warning(f"RAG unavailable: {e}")
        return patterns, knowledge

    async def call_tools(
        self,
        db: AsyncSession,
        conversation: Conversation,
        decision: AgentDecision,
        state: SalesState,
        products: List[Any],
    ) -> List[Dict[str, Any]]:
        """Execute the allowed tools via the Tool Registry (facts, not the LLM)."""
        registry = self._registry()
        context = ToolContext(
            db=db,
            conversation=conversation,
            state=state,
            customer_id=conversation.customer_id,
        )

        results: List[Dict[str, Any]] = []
        for name in decision.tool_calls:
            tool = registry.get(name)
            if tool is None:
                # Authorization: never execute a tool outside the registry.
                logger.warning(f"Unauthorized tool call blocked: {name}")
                results.append(
                    {
                        "tool": name,
                        "success": False,
                        "result": None,
                        "error": "unauthorized_tool",
                    }
                )
                continue
            arguments = self._tool_arguments(name, decision, state)
            result = await tool.execute(arguments, context)
            # Do not surface "missing product_id"-style errors when no argument
            # was available for the tool in the first place.
            if result.error and not arguments:
                continue
            results.append(result.to_dict(name))

        # Fast path for callers that preloaded a product list when no DB product row
        if (
            not results
            and products
            and decision.intent in (
                CustomerIntent.PRODUCT_RECOMMENDATION,
                CustomerIntent.PRICE_QUERY,
            )
        ):
            results.append(
                {
                    "tool": "search_products",
                    "success": True,
                    "result": {
                        "products": [
                            {
                                "product_id": str(p.id),
                                "name": p.name,
                                "price": float(p.price),
                                "stock_quantity": p.stock_quantity,
                            }
                            for p in products[:3]
                        ]
                    },
                    "error": None,
                }
            )
        return results

    def _tool_arguments(
        self, name: str, decision: AgentDecision, state: SalesState
    ) -> Dict[str, Any]:
        if name == "search_products":
            return {
                "budget": float(state.need.budget) if state.need.budget is not None else None,
                "limit": 3,
                "make": state.vehicle.make,
                "model": state.vehicle.model,
                "year": state.vehicle.year,
            }
        if name in ("get_product", "get_product_price", "get_product_stock"):
            if state.selected_product is not None and state.selected_product.product_id:
                return {"product_id": str(state.selected_product.product_id)}
            return {}
        if name == "create_order":
            return {"delivery_city": state.purchase.delivery_city}
        return {}

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
        history_messages: Optional[List[Any]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        prompt = _build_prompt(
            decision, text, state, patterns, knowledge, tools_facts, products,
            history_messages or [],
        )
        generation = None
        should_use_llm = allow_llm and _can_use_llm(
            decision, patterns, knowledge, tools_facts, products
        )
        if should_use_llm:
            generation = await self._call_llm(prompt)
        if generation is not None and generation["text"]:
            logger.info(
                f"LLM ok provider={generation.get('provider')} "
                f"model={generation.get('model')} latency_ms={generation.get('latency_ms')}"
            )
            return generation["text"], generation

        from app.ai.sales.transitions import next_question

        question = next_question(state) if state.missing_slots else None
        logger.warning("LLM reply unavailable — using rule/state fallback")
        return question or FALLBACK_ACK, None

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        try:
            start = time.monotonic()
            if self._llm_gateway is not None:
                raw = await asyncio.wait_for(self._llm_gateway(prompt), timeout=GENERATION_TIMEOUT)
                if isinstance(raw, dict):
                    return {
                        "text": str(raw.get("text", "")).strip(),
                        "provider": str(raw.get("provider", "test")),
                        "model": str(raw.get("model", "test")),
                        "latency_ms": int(raw.get("latency_ms", 0)),
                    }
                return {
                    "text": str(getattr(raw, "text", "")).strip(),
                    "provider": str(getattr(raw, "provider", "test")),
                    "model": str(getattr(raw, "model", "test")),
                    "latency_ms": int((time.monotonic() - start) * 1000),
                }

            from app.ai.llm.manager import LLMManager

            manager = LLMManager()
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
        tools: Optional[List[Dict[str, Any]]] = None,
        retrieved: Optional[List[Any]] = None,
    ) -> None:
        service = SalesStateService(db, cache=self.cache)
        await service.save(state, reason=decision.intent.value if decision.intent else "message")

        provider = (generation or {}).get("provider", "rule_fallback")
        model = (generation or {}).get("model", "fallback")
        latency_ms = (generation or {}).get("latency_ms", 0)

        run = AgentRun(
            conversation_id=conversation.id,
            model_provider=provider,
            model_name=model,
            prompt_version="seller-v1",
            state_before=state_before,
            state_after=state.to_dict(),
            retrieved_chunks=[str(r) for r in (retrieved or [])],
            response=reply,
            latency_ms=latency_ms,
        )
        db.add(run)
        await db.flush()

        for call in tools or []:
            db.add(
                ToolCall(
                    agent_run_id=run.id,
                    tool_name=str(call.get("tool")),
                    arguments={},
                    result=call.get("result"),
                    success=True,
                    latency_ms=None,
                )
            )
        await db.flush()


# --- pure helpers ----------------------------------------------------------


def _as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


# Intents whose reply must be grounded in tool/RAG facts; the LLM is not
# allowed to free-form such answers (it must never invent prices/fitment).
_CONTENT_INTENTS = {
    CustomerIntent.VEHICLE_COMPATIBILITY,
    CustomerIntent.PRODUCT_RECOMMENDATION,
    CustomerIntent.PRODUCT_COMPARISON,
    CustomerIntent.PRODUCT_INFO,
    CustomerIntent.PRICE_QUERY,
    CustomerIntent.PRICE_OBJECTION,
    CustomerIntent.PURCHASE_INTENT,
}


def _grounded(
    patterns: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    tools_facts: List[Dict[str, Any]],
    products: List[Any],
) -> bool:
    if patterns or knowledge or products:
        return True
    for call in tools_facts:
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("products") or result.get("policy") or result.get("matches"):
            return True
        if call.get("tool") == "check_compatibility" and result.get("verified") is not None:
            return True
    return False


def _can_use_llm(
    decision: AgentDecision,
    patterns: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    tools_facts: List[Dict[str, Any]],
    products: List[Any],
) -> bool:
    intent = decision.intent
    if intent is not None and intent not in _CONTENT_INTENTS:
        return True
    return _grounded(patterns, knowledge, tools_facts, products)


def _route_tools(intent: Optional[CustomerIntent]) -> List[str]:
    mapping = {
        CustomerIntent.VEHICLE_COMPATIBILITY: ["check_compatibility"],
        CustomerIntent.PRODUCT_RECOMMENDATION: ["search_products", "get_product_price"],
        CustomerIntent.PRODUCT_COMPARISON: ["search_products", "get_product_price"],
        CustomerIntent.PRODUCT_INFO: ["search_products"],
        CustomerIntent.PRICE_QUERY: ["search_products", "get_product_price"],
        CustomerIntent.PRICE_OBJECTION: ["search_products", "get_product_price"],
        CustomerIntent.TRUST_OBJECTION: ["get_warranty_info"],
        CustomerIntent.DELIVERY_QUERY: ["get_delivery_info"],
        CustomerIntent.WARRANTY_QUERY: ["get_warranty_info"],
        CustomerIntent.PURCHASE_INTENT: ["search_products"],
        CustomerIntent.ORDER_REQUEST: ["create_order"],
        CustomerIntent.HANDOFF_REQUEST: ["request_handoff"],
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


def _strip_stock(value: Any) -> Any:
    """Remove inventory counters recursively before anything is shown to the LLM."""
    if isinstance(value, dict):
        return {
            k: _strip_stock(v)
            for k, v in value.items()
            if k not in ("stock_quantity", "quantity")
        }
    if isinstance(value, list):
        return [_strip_stock(v) for v in value]
    return value


def _build_prompt(
    decision: AgentDecision,
    text: str,
    state: SalesState,
    patterns: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    tools_facts: List[Dict[str, Any]],
    products: List[Any],
    history_messages: Optional[List[Any]] = None,
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

    # The last history item is usually the just-saved current message.
    history = (history_messages or [])[:-1]
    history_lines = []
    for msg in history:
        role = "Клиент" if getattr(msg, "sender_type", "") == "customer" else "Продавец"
        history_lines.append(f"{role}: {getattr(msg, 'text', '')}")
    history_block = "\n".join(history_lines)

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
        tools_lines.append(
            f"{call['tool']}: {json.dumps(_strip_stock(call['result']), ensure_ascii=False)}"
        )
    tools_block = "\n".join(tools_lines)

    products_block = "\n".join(
        f"- {p.name} — {float(p.price)} ₽"
        for p in products[:3]
    )

    return f"""Ты — профессиональный продавец-консультант магазина светодиодных линз и би-лед модулей.
Твоя задача — не просто консультировать, а продать: подтвердить выбор клиента и довести до заказа и оплаты.

Правила:
- Общайся естественно и по делу, как менеджер в чате: коротко, но живо.
- Веди диалог с учётом ИСТОРИИ ниже: не повторяй уже заданные вопросы и сказанное.
- Все товары каталога ВСЕГДА в наличии. Никогда не говори «нет в наличии», «закончился», «отсутствует», «под заказ».
- НЕ выдумывай цену, характеристики, совместимость, гарантию или сроки; бери их только из проверенных данных инструментов и «Доступных товаров».
- Если в данных инструмента confirmed_for_vehicle=false (или такого поля нет) — это товар из общего ассортимента: не заявляй, что он точно совместим с авто клиента.
- Если данных не хватает — задай ОДИН уточняющий вопрос по существу.
- Клиент выбрал вариант («первый», «этот», «беру», назвал модель) — не возвращайся к вопросам о потребности и бюджете: подтверди выбор и переходи к оформлению (количество, установка, доставка, оплата).
- Продавай мягко, предлагай подходящие варианты и веди к оформлению заказа.

Намерение: {decision.intent.value if decision.intent else 'general'}
Этап: {decision.stage.value} (стратегия: {decision.response_strategy})

История диалога:
{history_block if history_block else '- новый диалог'}

Известно о клиенте:
{chr(10).join(known) if known else '- пока ничего'}

Поведенческие паттерны (Sales RAG, перенимай подход, не копируй):
{patterns_block or '- нет'}

Факты (Knowledge RAG, используй только их):
{facts_block or '- нет'}

Проверенные данные инструментов (цены/наличие):
{tools_block or '- нет'}

Доступные товары:
{products_block or '- нет'}

Сообщение клиента: {text}"""
