"""Prompt Builder - builds prompts for LLM based on context."""

import json
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PromptBuilder:
    """Builds prompts for LLM based on conversation context."""

    def __init__(self):
        """Initialize prompt builder."""
        self.system_prompt = self._load_system_prompt()
        self.sales_prompt = self._load_sales_prompt()
        self.personality_prompt = self._load_personality_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from file or use default."""
        try:
            with open("app/ai/prompts/system_prompt.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return self._get_default_system_prompt()

    def _load_sales_prompt(self) -> str:
        """Load sales prompt from file or use default."""
        try:
            with open("app/ai/prompts/sales_prompt.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return self._get_default_sales_prompt()

    def _load_personality_prompt(self) -> str:
        """Load personality prompt from file or use default."""
        try:
            with open("app/ai/prompts/personality_prompt.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return self._get_default_personality_prompt()

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt."""
        return """Ты — профессиональный продавец-консультант светодиодных линз для автомобилей. 
Твоя задача — помочь клиенту подобрать подходящие линзы, ответить на вопросы, 
работать с возражениями и помочь оформить заказ.

Основные правила:
1. Всегда будь вежливым и профессиональным
2. Не изобретай факты о товарах — используй только ту информацию, которая есть в базе знаний
3. Если не знаешь ответа — признай это и предложи уточнить или передать менеджеру
4. Работай с возражениями клиента, а не спори с ним
5. Помоги клиенту принять решение, а не продавай любой ценой

Ты работаешь в магазине: {shop_name}
Язык общения: {language}"""

    def _get_default_sales_prompt(self) -> str:
        """Get default sales prompt."""
        return """Следуй этим принципам продаж:
1. Сначала выяви потребность клиента
2. Уточняй детали: марка, модель, год автомобиля, тип фар
3. Предлагай подходящие варианты с объяснением
4. Работай с возражениями: признай, уточни, предложи альтернативу
5. Закрывай сделку: уточняй детали заказа, подтверждай выбор

Типичные возражения и как с ними работать:
- "Дорого": Уточни бюджет, объясни ценность, предложи альтернативу
- "Не подходит": Проверь совместимость, уточни детали автомобиля
- "Не доверяю": Предоставь факты, гарантии, отзывы
- "Хочу подумать": Зафиксируй варианты, предложи сравнение"""

    def _get_default_personality_prompt(self) -> str:
        """Get default personality prompt."""
        return """Твой стиль общения:
- Профессиональный и компетентный
- Вежливый и терпеливый
- Четкий и лаконичный
- Помогающий, а не навязывающий
- Открытый к вопросам и возражениям

Не используй:
- Сленг и жаргон
- Слишком длинные предложения
- Агрессивные техник продаж
- Нечестные обещания"""

    async def build_prompt(
        self,
        message: str,
        intent: str,
        sales_state: str,
        context: Dict[str, Any],
        rag_context: Dict[str, Any],
        product_context: Dict[str, Any],
    ) -> str:
        """Build complete prompt for LLM."""
        # Build prompt components
        prompt_parts = []
        
        # System prompt
        system_prompt = self._format_system_prompt(context)
        prompt_parts.append(f"<system>{system_prompt}</system>")
        
        # Personality prompt
        personality_prompt = self._format_personality_prompt(context)
        prompt_parts.append(f"<personality>{personality_prompt}</personality>")
        
        # Sales prompt
        sales_prompt = self._format_sales_prompt(sales_state, intent)
        prompt_parts.append(f"<sales>{sales_prompt}</sales>")
        
        # Conversation context
        conversation_context = self._format_conversation_context(context)
        if conversation_context:
            prompt_parts.append(f"<conversation>{conversation_context}</conversation>")
        
        # Customer context
        customer_context = self._format_customer_context(context)
        if customer_context:
            prompt_parts.append(f"<customer>{customer_context}</customer>")
        
        # RAG context
        rag_context_str = self._format_rag_context(rag_context)
        if rag_context_str:
            prompt_parts.append(f"<knowledge>{rag_context_str}</knowledge>")
        
        # Product context
        product_context_str = self._format_product_context(product_context)
        if product_context_str:
            prompt_parts.append(f"<products>{product_context_str}</products>")
        
        # Current message
        prompt_parts.append(f"<user>{message}</user>")
        
        # Instructions
        prompt_parts.append(self._get_instructions(sales_state, intent))
        
        # Combine all parts
        full_prompt = "\n\n".join(prompt_parts)
        
        logger.debug(f"Built prompt (truncated): {full_prompt[:200]}...")
        
        return full_prompt

    def _format_system_prompt(self, context: Dict[str, Any]) -> str:
        """Format system prompt with context."""
        shop_name = context.get("shop_name", "AI Seller")
        language = context.get("language", settings.default_language)
        
        return self.system_prompt.format(
            shop_name=shop_name,
            language=language,
        )

    def _format_personality_prompt(self, context: Dict[str, Any]) -> str:
        """Format personality prompt with context."""
        tone = context.get("tone", settings.agent_tone)
        
        # Customize based on tone
        if tone == "friendly":
            return self.personality_prompt + "\nБудь дружелюбным и открытым."
        elif tone == "professional":
            return self.personality_prompt + "\nСоблюдай деловой стиль общения."
        elif tone == "technical":
            return self.personality_prompt + "\nМожешь использовать технические детали при необходимости."
        
        return self.personality_prompt

    def _format_sales_prompt(self, sales_state: str, intent: str) -> str:
        """Format sales prompt based on current state and intent."""
        # Add state-specific instructions
        state_instructions = {
            "greeting": "Приветствуй клиента и начни выявлять потребность.",
            "discovery": "Задавай уточняющие вопросы, чтобы понять потребности клиента.",
            "qualification": "Уточняй детали автомобиля и бюджета.",
            "recommendation": "Предлагай подходящие варианты с объяснением.",
            "objection": "Работай с возражением: признай, уточни, предложи решение.",
            "negotiation": "Помоги клиенту принять решение, объясняя преимущества.",
            "closing": "Закрывай сделку: уточняй детали заказа.",
        }
        
        base_prompt = self.sales_prompt
        state_instruction = state_instructions.get(sales_state, "")
        
        if state_instruction:
            base_prompt += f"\n\nТекущий этап: {sales_state}. {state_instruction}"
        
        # Add intent-specific instructions
        intent_instructions = {
            "price_objection": "Клиент считает цену высокой. Не защищай цену сразу — уточни бюджет и объясни ценность.",
            "compatibility": "Клиент спрашивает о совместимости. Проверь данные и дай точный ответ.",
            "order_intent": "Клиент хочет оформить заказ. Уточни детали и подтверди выбор.",
        }
        
        intent_instruction = intent_instructions.get(intent, "")
        if intent_instruction:
            base_prompt += f"\n\nНамерение клиента: {intent}. {intent_instruction}"
        
        return base_prompt

    def _format_conversation_context(self, context: Dict[str, Any]) -> str:
        """Format conversation context."""
        messages = context.get("messages", [])
        
        if not messages:
            return ""
        
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted_messages.append(f"{role.capitalize()}: {content}")
        
        return "\n".join(formatted_messages)

    def _format_customer_context(self, context: Dict[str, Any]) -> str:
        """Format customer context."""
        customer_profile = context.get("customer_profile", {})
        
        parts = []
        
        if customer_profile.get("name"):
            parts.append(f"Имя: {customer_profile['name']}")
        
        if customer_profile.get("vehicle"):
            parts.append(f"Автомобиль: {customer_profile['vehicle']}")
        
        if customer_profile.get("budget_min") or customer_profile.get("budget_max"):
            budget_min = customer_profile.get("budget_min", 0)
            budget_max = customer_profile.get("budget_max", 0)
            parts.append(f"Бюджет: {budget_min}–{budget_max} ₽")
        
        if customer_profile.get("customer_type"):
            parts.append(f"Тип клиента: {customer_profile['customer_type']}")
        
        if customer_profile.get("facts"):
            facts = customer_profile["facts"]
            parts.append(f"Факты: {', '.join(f'{k}: {v}' for k, v in facts.items())}")
        
        return "\n".join(parts) if parts else ""

    def _parse_json_list(self, value: Any) -> List[str]:
        """Parse a JSON-encoded list or return a plain list of strings."""
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
        return []

    def _format_rag_context(self, rag_context: Dict[str, Any]) -> str:
        """Format RAG context."""
        parts = []

        # Knowledge context
        knowledge = rag_context.get("knowledge", [])
        if knowledge:
            parts.append("Знания (факты из базы знаний — используй только их, не выдумывай):")
            for item in knowledge[:3]:  # Top 3
                content = (item.get("content") or item.get("text") or "").strip()
                if content:
                    parts.append(f"- {content[:400]}")

        # Sales patterns context
        sales_patterns = rag_context.get("sales_patterns", [])
        if sales_patterns:
            parts.append("\nПоведенческие паттерны продавца (Sales RAG):")
            parts.append("Не копируй их дословно — перенимай подход, тон и логику диалога.")
            for idx, pattern in enumerate(sales_patterns[:3], start=1):  # Top 3
                label = pattern.get("label", "positive")
                header = f"Паттерн {idx}"
                if label == "negative":
                    header += " — ПРИМЕР НЕПРАВИЛЬНОГО ОТВЕТА, так делать нельзя"
                parts.append(header)

                dialogue = pattern.get("dialogue")
                if isinstance(dialogue, str):
                    try:
                        dialogue = json.loads(dialogue)
                    except (ValueError, TypeError):
                        dialogue = None

                if isinstance(dialogue, list):
                    for msg in dialogue[:6]:
                        role = "Клиент" if msg.get("role") == "customer" else "Продавец"
                        text = (msg.get("text") or "").strip()
                        if text:
                            parts.append(f"  {role}: {text[:220]}")

                strategy = self._parse_json_list(pattern.get("successful_strategy"))
                if strategy:
                    parts.append(f"  Стратегия: {', '.join(strategy[:6])}")

                mistakes = self._parse_json_list(pattern.get("mistakes_to_avoid"))
                if mistakes:
                    parts.append(f"  Чего избегать: {', '.join(mistakes[:6])}")

        return "\n".join(parts) if parts else ""

    def _format_product_context(self, product_context: Dict[str, Any]) -> str:
        """Format product context."""
        products = product_context.get("relevant_products", [])
        
        if not products:
            return ""
        
        parts = ["Подходящие товары:"]
        for product in products[:5]:  # Top 5
            parts.append(
                f"- {product.get('name', 'Неизвестно')} "
                f"({product.get('brand', '')}) "
                f"- {product.get('price', 0)} ₽"
            )
        
        return "\n".join(parts)

    def _get_instructions(self, sales_state: str, intent: str) -> str:
        """Get final instructions for LLM."""
        instructions = [
            "Ответь на сообщение клиента.",
            "Будь вежливым и профессиональным.",
            "Используй информацию из контекста.",
        ]
        
        # Add state-specific instructions
        if sales_state == "objection":
            instructions.append("Работай с возражением клиента.")
        elif sales_state == "closing":
            instructions.append("Помоги клиенту оформить заказ.")
        
        # Add intent-specific instructions
        if intent == "price_objection":
            instructions.append("Не защищай цену — уточняй бюджет и объясняй ценность.")
        
        instructions.append("Ответь на русском языке.")
        
        return "\n".join(instructions)

    async def build_chat_prompt(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Build chat-style prompt for LLM."""
        # Start with system message
        system_message = self._format_system_prompt(context)
        
        chat_messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Add personality
        personality = self._format_personality_prompt(context)
        chat_messages.append(
            {"role": "system", "content": f"Стиль общения: {personality}"}
        )
        
        # Add sales context
        sales_state = context.get("sales_state", "new")
        intent = context.get("intent", "general")
        sales_context = self._format_sales_prompt(sales_state, intent)
        chat_messages.append(
            {"role": "system", "content": f"Контекст продаж: {sales_context}"}
        )
        
        # Add customer context
        customer_context = self._format_customer_context(context)
        if customer_context:
            chat_messages.append(
                {"role": "system", "content": f"Информация о клиенте: {customer_context}"}
            )
        
        # Add product context
        product_context = context.get("product_context", {})
        product_context_str = self._format_product_context(product_context)
        if product_context_str:
            chat_messages.append(
                {"role": "system", "content": f"Информация о товарах: {product_context_str}"}
            )
        
        # Add conversation history
        chat_messages.extend(messages)
        
        return chat_messages
