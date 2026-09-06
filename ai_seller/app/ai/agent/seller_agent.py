"""Seller Agent - main AI agent for sales conversations."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.models.conversation import (
    Conversation,
    Message,
    SalesState,
    SenderType,
    MessageType,
)
from app.infrastructure.database.models.customer import Customer, CustomerProfile
from app.infrastructure.database.models.product import Product, Compatibility
from app.ai.rag.retriever import RAGRetriever
from app.ai.memory.conversation import ConversationMemory
from app.ai.prompts.prompt_builder import PromptBuilder
from app.ai.llm.manager import LLMManager

logger = get_logger(__name__)


class AgentResponse:
    """Response from the Seller Agent."""

    def __init__(
        self,
        text: str,
        products: Optional[List[Dict[str, Any]]] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        handoff: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.text = text
        self.products = products or []
        self.actions = actions or []
        self.handoff = handoff
        self.metadata = metadata or {}


class SellerAgent:
    """Main AI Seller Agent."""

    def __init__(
        self,
        rag_retriever: Optional[RAGRetriever] = None,
        conversation_memory: Optional[ConversationMemory] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_manager: Optional[LLMManager] = None,
    ):
        """Initialize the Seller Agent."""
        self.rag_retriever = rag_retriever or RAGRetriever()
        self.conversation_memory = conversation_memory or ConversationMemory()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm_manager = llm_manager or LLMManager()
        
    async def process_message(
        self,
        message: str,
        conversation: Conversation,
        customer: Optional[Customer] = None,
        available_products: Optional[List[Product]] = None,
    ) -> AgentResponse:
        """Process a customer message and generate a response."""
        logger.info(f"Processing message: {message[:50]}... in conversation {conversation.id}")
        
        try:
            # Step 1: Load conversation context
            context = await self._build_context(conversation, customer)
            
            # Step 2: Detect intent and update sales state
            intent, sales_state = await self._detect_intent(message, context)
            
            # Step 3: Retrieve relevant information
            rag_context = await self._retrieve_rag_context(message, intent, sales_state, context)
            product_context = await self._retrieve_product_context(
                message, intent, available_products, context
            )
            
            # Step 4: Build prompt
            prompt = await self._build_prompt(
                message, intent, sales_state, context, rag_context, product_context
            )
            
            # Attach products to context so the final response can include them
            context["relevant_products"] = product_context.get("relevant_products", [])
            
            # Step 5: Generate response
            response_text, metadata = await self._generate_response(prompt)
            
            # Step 6: Validate and post-process response
            final_response = await self._post_process_response(
                response_text, metadata, intent, sales_state, context
            )
            
            # Step 7: Update conversation state
            await self._update_conversation_state(conversation, sales_state, intent, final_response)
            
            logger.info(f"Generated response: {response_text[:50]}...")
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return AgentResponse(
                text="Извините, произошла ошибка. Пожалуйста, попробуйте позже.",
                handoff=True,
                metadata={"error": str(e)},
            )

    async def _build_context(
        self, conversation: Conversation, customer: Optional[Customer]
    ) -> Dict[str, Any]:
        """Build conversation context."""
        context = {
            "conversation_id": str(conversation.id),
            "customer_id": str(conversation.customer_id),
            "shop_id": str(conversation.shop_id),
            "channel": conversation.channel,
            "sales_state": conversation.sales_state,
            "status": conversation.status,
            "messages": [],
            "customer_profile": {},
        }
        
        # Load recent messages
        recent_messages = await self.conversation_memory.get_recent_messages(
            conversation.id, limit=10
        )
        context["messages"] = [
            {"role": "customer" if msg.sender_type == SenderType.CUSTOMER else "assistant",
             "content": msg.text}
            for msg in recent_messages
        ]
        
        # Load customer profile
        if customer:
            context["customer_profile"] = {
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "telegram_user_id": customer.telegram_user_id,
            }
            
            if customer.profile:
                context["customer_profile"].update({
                    "vehicle": customer.profile.vehicle.model if customer.profile.vehicle else None,
                    "budget_min": customer.profile.budget_min,
                    "budget_max": customer.profile.budget_max,
                    "customer_type": customer.profile.customer_type,
                    "preferences": customer.profile.preferences,
                    "facts": customer.profile.facts,
                })
        
        return context

    async def _detect_intent(
        self, message: str, context: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Detect intent and determine sales state."""
        # This is a simplified version - in production, use a proper intent classifier
        message_lower = message.lower()
        
        # Detect intent
        if any(greeting in message_lower for greeting in ["здравствуйте", "привет", "добрый день", "добрый вечер"]):
            intent = "greeting"
        elif any(question in message_lower for question in ["сколько стоит", "цена", "стоимость"]):
            intent = "price_inquiry"
        elif any(question in message_lower for question in ["почему так дорого", "дорого", "кусается"]):
            intent = "price_objection"
        elif any(question in message_lower for question in ["есть в наличии", "наличие", "когда будет"]):
            intent = "availability"
        elif any(question in message_lower for question in ["подходит", "совместимость", "встанет"]):
            intent = "compatibility"
        elif any(question in message_lower for question in ["что посоветуете", "какие лучше", "рекомендация"]):
            intent = "recommendation"
        elif any(question in message_lower for question in ["хочу заказать", "оформить заказ", "беру"]):
            intent = "order_intent"
        else:
            intent = "general_question"
        
        # Determine sales state based on current state and intent
        current_state = context.get("sales_state", SalesState.NEW)
        
        if current_state == SalesState.NEW and intent == "greeting":
            sales_state = SalesState.GREETING
        elif current_state in [SalesState.NEW, SalesState.GREETING] and intent in ["price_inquiry", "general_question"]:
            sales_state = SalesState.DISCOVERY
        elif current_state == SalesState.DISCOVERY and intent == "price_objection":
            sales_state = SalesState.OBJECTION
        elif current_state == SalesState.DISCOVERY and intent == "recommendation":
            sales_state = SalesState.RECOMMENDATION
        elif intent == "order_intent":
            sales_state = SalesState.CLOSING
        else:
            sales_state = current_state
        
        return intent, sales_state

    async def _retrieve_rag_context(
        self,
        message: str,
        intent: str,
        sales_state: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Retrieve relevant context from RAG."""
        rag_context = {
            "knowledge": [],
            "sales_patterns": [],
        }
        
        if settings.rag_enabled:
            try:
                # Retrieve knowledge RAG
                if intent in ["price_objection", "price_inquiry", "compatibility",
                              "availability", "general_question", "product_info"]:
                    knowledge_results = await self.rag_retriever.search_knowledge(
                        query=message,
                        limit=3,
                    )
                    rag_context["knowledge"] = knowledge_results

                # Retrieve sales RAG — use behavioral patterns in most sales states,
                # not only for objections/closing.
                sales_intents = {
                    "greeting", "recommendation", "price_inquiry", "price_objection",
                    "availability", "compatibility", "order_intent",
                }
                sales_states = {
                    SalesState.DISCOVERY,
                    SalesState.QUALIFICATION,
                    SalesState.RECOMMENDATION,
                    SalesState.OBJECTION,
                    SalesState.NEGOTIATION,
                    SalesState.CLOSING,
                    SalesState.ORDER,
                }
                if intent in sales_intents or sales_state in sales_states:
                    sales_results = await self.rag_retriever.search_sales_dialogues(
                        query=message,
                        intent=intent,
                        sales_state=sales_state,
                        customer_type=context.get("customer_profile", {}).get("customer_type"),
                        limit=3,
                    )
                    rag_context["sales_patterns"] = sales_results

            except Exception as e:
                logger.warning(f"RAG retrieval error: {e}")
        
        return rag_context

    async def _retrieve_product_context(
        self,
        message: str,
        intent: str,
        available_products: Optional[List[Product]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Retrieve relevant product context."""
        product_context = {
            "relevant_products": [],
            "compatibility_info": None,
        }
        
        if not available_products:
            return product_context

        # If we have vehicle information, check compatibility
        customer_profile = context.get("customer_profile", {})
        vehicle_info = customer_profile.get("vehicle")

        candidates: List[Product] = []
        if vehicle_info and intent in ["compatibility", "recommendation", "price_inquiry",
                                       "availability", "general_question"]:
            # Products that have at least one confirmed non-negative compatibility
            for product in available_products:
                confirmed = [
                    c for c in (product.compatibilities or [])
                    if c.is_confirmed and c.type != "not_recommended"
                ]
                if confirmed:
                    candidates.append(product)
        elif intent in ["recommendation", "price_inquiry", "availability", "general_question",
                        "price_objection"]:
            # No vehicle known yet — still allow well-informed suggestions
            candidates = available_products

        # Order candidates by price and take the top 5
        candidates.sort(key=lambda p: float(p.price) if p.price is not None else 0.0)
        product_context["relevant_products"] = [
            {
                "id": str(p.id),
                "name": p.name,
                "price": float(p.price) if p.price is not None else 0.0,
                "brand": p.brand,
                "category": p.category,
                "stock_quantity": p.stock_quantity,
                "specifications": p.specifications,
            }
            for p in candidates[:5]
        ]

        return product_context

    async def _build_prompt(
        self,
        message: str,
        intent: str,
        sales_state: str,
        context: Dict[str, Any],
        rag_context: Dict[str, Any],
        product_context: Dict[str, Any],
    ) -> str:
        """Build the prompt for LLM."""
        return await self.prompt_builder.build_prompt(
            message=message,
            intent=intent,
            sales_state=sales_state,
            context=context,
            rag_context=rag_context,
            product_context=product_context,
        )

    async def _generate_response(
        self, prompt: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate response using LLM."""
        try:
            response = await self.llm_manager.generate(
                prompt=prompt,
                temperature=settings.agent_temperature,
                max_tokens=settings.agent_max_tokens,
            )
            return response.text, response.metadata
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "Извините, не могу сгенерировать ответ.", {}

    async def _post_process_response(
        self,
        response_text: str,
        metadata: Dict[str, Any],
        intent: str,
        sales_state: str,
        context: Dict[str, Any],
    ) -> AgentResponse:
        """Post-process the response."""
        # Clean up response
        response_text = response_text.strip()
        
        # Check for handoff conditions
        handoff = False
        if "не знаю" in response_text.lower() or "не могу" in response_text.lower():
            handoff = True
        
        # Check if we should recommend products
        products = []
        if intent == "recommendation" and context.get("relevant_products"):
            products = context["relevant_products"][:3]  # Top 3 recommendations
        
        # Check for actions (buttons, links, etc.)
        actions = []
        if sales_state == SalesState.CLOSING:
            actions.append({
                "type": "order",
                "label": "Оформить заказ",
                "action": "create_order",
            })
        
        return AgentResponse(
            text=response_text,
            products=products,
            actions=actions,
            handoff=handoff,
            metadata={
                "intent": intent,
                "sales_state": sales_state,
                **metadata,
            },
        )

    async def _update_conversation_state(
        self,
        conversation: Conversation,
        sales_state: str,
        intent: str,
        response: AgentResponse,
    ) -> None:
        """Update conversation state."""
        conversation.sales_state = sales_state
        
        # Update summary if needed
        if response.metadata.get("should_update_summary"):
            conversation.summary = response.text[:200]  # Truncate to 200 chars
        
        # If handoff, update status
        if response.handoff:
            conversation.status = "waiting_manager"
