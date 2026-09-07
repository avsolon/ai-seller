"""Channel-agnostic messaging application service (doc 12).

Handles: idempotency -> conversation resolve -> SellerAgent -> persistence
(Message rows) -> optional manager_task on handoff.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.dto import IncomingMessage, MessageChannel, OutgoingMessage
from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import (
    Conversation,
    Message,
    MessageType,
    SenderType,
)
from app.infrastructure.database.models.customer import Customer, CustomerExternalID
from app.infrastructure.database.models.manager_task import ManagerTask, ManagerTaskStatus
from app.infrastructure.database.models.shop import Shop, ShopStatus

logger = get_logger(__name__)

AgentCallable = Callable[[AsyncSession, Conversation, str], Awaitable[str]]


async def _default_agent(db: AsyncSession, conversation: Conversation, text: str) -> str:
    from app.ai.agent.orchestrator import process_message

    result = await process_message(db=db, conversation=conversation, text=text)
    return result.get("reply", "")


async def _default_shop(db: AsyncSession) -> Shop:
    result = await db.execute(select(Shop).where(Shop.slug == settings.shop_id))
    shop = result.scalar_one_or_none()
    if shop is None:
        shop = Shop(
            slug=settings.shop_id,
            name="AI Seller Shop",
            status=ShopStatus.ACTIVE,
            timezone="UTC",
            default_language=settings.default_language,
        )
        db.add(shop)
        await db.flush()
    return shop


async def _default_agent_for(db: AsyncSession, shop_id: UUID) -> Agent:
    result = await db.execute(select(Agent).where(Agent.shop_id == shop_id).limit(1))
    agent = result.scalar_one_or_none()
    if agent is None:
        agent = Agent(shop_id=shop_id, name="Default Agent", status="active")
        db.add(agent)
        await db.flush()
    return agent


class ConversationResolver:
    """Resolves Customer + Conversation (and external ids) from an IncomingMessage."""

    async def resolve(
        self, db: AsyncSession, message: IncomingMessage
    ) -> Conversation:
        customer = await self._get_or_create_customer(db, message)
        conversation = await self._get_active_conversation(db, message)
        if conversation is not None:
            return conversation

        shop = await _default_shop(db)
        agent = await _default_agent_for(db, shop.id)
        conversation = Conversation(
            shop_id=shop.id,
            customer_id=customer.id,
            agent_id=agent.id,
            channel=message.channel.value,
            external_session_id=message.external_conversation_id,
            status="active",
            sales_state="NEW",
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def _get_or_create_customer(
        self, db: AsyncSession, message: IncomingMessage
    ) -> Customer:
        result = await db.execute(
            select(Customer)
            .join(CustomerExternalID, CustomerExternalID.customer_id == Customer.id)
            .where(
                CustomerExternalID.channel == message.channel.value,
                CustomerExternalID.external_id == message.external_user_id,
            )
        )
        customer = result.scalar_one_or_none()
        if customer is not None:
            return customer

        shop = await _default_shop(db)
        customer = Customer(shop_id=shop.id)
        db.add(customer)
        await db.flush()
        db.add(
            CustomerExternalID(
                customer_id=customer.id,
                channel=message.channel.value,
                external_id=message.external_user_id,
            )
        )
        await db.flush()
        return customer

    async def _get_active_conversation(
        self, db: AsyncSession, message: IncomingMessage
    ) -> Optional[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.channel == message.channel.value,
                Conversation.external_session_id == message.external_conversation_id,
                Conversation.status == "active",
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class MessageApplicationService:
    """Orchestrates one incoming channel message end-to-end."""

    def __init__(
        self,
        agent: Optional[AgentCallable] = None,
        conversation_resolver: Optional[ConversationResolver] = None,
    ) -> None:
        self.agent = agent or _default_agent
        self.resolver = conversation_resolver or ConversationResolver()

    async def handle(
        self, db: AsyncSession, message: IncomingMessage
    ) -> OutgoingMessage:
        # Idempotency: the same (channel, external_message_id) is handled once.
        if await self._is_processed(db, message):
            return OutgoingMessage(text="")

        conversation = await self.resolver.resolve(db, message)

        text = (message.text or "").strip()
        if not text and not message.attachments:
            return OutgoingMessage(
                text="Напишите, для какого автомобиля подбираете линзы.", 
                metadata={"conversation_id": str(conversation.id)},
            )

        try:
            # Persist the customer message first (this row is the idempotency key)
            user_message = Message(
                conversation_id=conversation.id,
                sender_type=SenderType.CUSTOMER,
                message_type=MessageType.TEXT,
                channel=message.channel.value,
                text=text or "📷 фото",
                external_message_id=message.external_message_id,
                meta={},
            )
            db.add(user_message)
            await db.flush()
        except IntegrityError:
            # A concurrent webhook already processed this message
            await db.rollback()
            return OutgoingMessage(text="")

        try:
            reply = await self.agent(db, conversation, text)
        except Exception as e:
            logger.exception("agent processing failed", exc_info=e)
            reply = (
                "Сейчас не удалось получить информацию. "
                "Давайте попробуем ещё раз."
            )

        db.add(
            Message(
                conversation_id=conversation.id,
                sender_type=SenderType.AGENT,
                message_type=MessageType.TEXT,
                channel=message.channel.value,
                text=reply,
                meta={},
            )
        )
        await db.flush()

        if conversation.status == "handed_off":
            await self._ensure_manager_task(db, conversation.id, reason="agent_handoff")

        return OutgoingMessage(
            text=reply, metadata={"conversation_id": str(conversation.id)}
        )

    async def request_handoff(
        self, db: AsyncSession, conversation: Conversation, reason: str = "customer_requested_manager"
    ) -> None:
        conversation.status = "handed_off"
        await db.flush()
        await self._ensure_manager_task(db, conversation.id, reason=reason)

    async def _is_processed(
        self, db: AsyncSession, message: IncomingMessage
    ) -> bool:
        result = await db.execute(
            select(func.count())
            .select_from(Message)
            .where(
                Message.channel == message.channel.value,
                Message.external_message_id == message.external_message_id,
            )
        )
        return bool(result.scalar_one())

    async def _ensure_manager_task(
        self, db: AsyncSession, conversation_id: UUID, reason: str
    ) -> None:
        open_tasks = await db.execute(
            select(func.count())
            .select_from(ManagerTask)
            .where(
                ManagerTask.conversation_id == conversation_id,
                ManagerTask.status == ManagerTaskStatus.OPEN,
            )
        )
        if open_tasks.scalar_one():
            return
        db.add(
            ManagerTask(
                conversation_id=conversation_id,
                type="handoff",
                status=ManagerTaskStatus.OPEN,
                reason=reason,
            )
        )
        await db.flush()
