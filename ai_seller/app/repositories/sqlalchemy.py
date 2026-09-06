"""SQLAlchemy implementations of the repository interfaces."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.conversation import Conversation, Message
from app.infrastructure.database.models.customer import Customer, CustomerExternalID
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.sales_state import SalesStateRecord, StateTransition


class SqlCustomerRepository:
    """Customer repository backed by an async SQLAlchemy session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, customer_id: UUID) -> Optional[Customer]:
        return await self.db.get(Customer, customer_id)

    async def find_by_external(self, channel: str, external_id: str) -> Optional[Customer]:
        result = await self.db.execute(
            select(Customer)
            .join(CustomerExternalID, CustomerExternalID.customer_id == Customer.id)
            .where(
                CustomerExternalID.channel == channel,
                CustomerExternalID.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, customer: Customer) -> Customer:
        self.db.add(customer)
        await self.db.flush()
        return customer

    async def add_external_id(
        self, customer_id: UUID, channel: str, external_id: str
    ) -> CustomerExternalID:
        record = CustomerExternalID(
            customer_id=customer_id, channel=channel, external_id=external_id
        )
        self.db.add(record)
        await self.db.flush()
        return record


class SqlConversationRepository:
    """Conversation repository backed by an async SQLAlchemy session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, conversation_id: UUID) -> Optional[Conversation]:
        return await self.db.get(Conversation, conversation_id)

    async def get_active_by_customer(
        self, customer_id: UUID, channel: Optional[str] = None
    ) -> Optional[Conversation]:
        query = select(Conversation).where(
            Conversation.customer_id == customer_id,
            Conversation.status == "active",
        )
        if channel:
            query = query.where(Conversation.channel == channel)
        query = query.order_by(Conversation.created_at.desc()).limit(1)
        return (await self.db.execute(query)).scalar_one_or_none()

    async def create(self, conversation: Conversation) -> Conversation:
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def update_status(self, conversation: Conversation, status: str) -> Conversation:
        conversation.status = status
        await self.db.flush()
        return conversation

    async def touch(self, conversation: Conversation) -> None:
        conversation.last_message_at = conversation.updated_at
        await self.db.flush()


class SqlMessageRepository:
    """Message repository backed by an async SQLAlchemy session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, message: Message) -> Message:
        self.db.add(message)
        await self.db.flush()
        return message

    async def list_by_conversation(
        self, conversation_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())[::-1]


class SqlProductRepository:
    """Product repository backed by an async SQLAlchemy session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, product_id: UUID) -> Optional[Product]:
        return await self.db.get(Product, product_id)

    async def get_by_sku(self, shop_id: UUID, sku: str) -> Optional[Product]:
        result = await self.db.execute(
            select(Product).where(Product.shop_id == shop_id, Product.sku == sku)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        shop_id: Optional[UUID] = None,
        search: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Product]:
        query = select(Product)
        if active_only:
            query = query.where(Product.is_active.is_(True))
        if shop_id is not None:
            query = query.where(Product.shop_id == shop_id)
        if category:
            query = query.where(Product.category == category)
        if search:
            like = f"%{search.lower()}%"
            query = query.where(
                or_(
                    Product.name.ilike(like),
                    Product.sku.ilike(like),
                    Product.brand.ilike(like),
                )
            )
        query = query.order_by(Product.category, Product.price).offset(offset).limit(limit)
        return list((await self.db.execute(query)).scalars().all())


class SqlSalesStateRepository:
    """SalesState repository backed by an async SQLAlchemy session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_conversation(self, conversation_id: UUID) -> Optional[SalesStateRecord]:
        result = await self.db.execute(
            select(SalesStateRecord).where(
                SalesStateRecord.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, state: SalesStateRecord) -> SalesStateRecord:
        """Optimistic upsert: bumps version only when the stored version matches."""
        existing = await self.get_by_conversation(state.conversation_id)
        if existing is None:
            state.version = 1
            self.db.add(state)
            await self.db.flush()
            return state

        expected = state.version
        existing.stage = state.stage
        existing.intent = state.intent
        existing.emotion = state.emotion
        existing.customer_type = state.customer_type
        existing.vehicle = state.vehicle
        existing.need = state.need
        existing.purchase = state.purchase
        existing.objections = state.objections
        existing.missing_slots = state.missing_slots
        existing.selected_product_id = state.selected_product_id
        existing.purchase_intent_score = state.purchase_intent_score
        existing.handoff_requested = state.handoff_requested
        existing.version = expected + 1
        await self.db.flush()
        return existing

    async def add_transition(self, transition: StateTransition) -> StateTransition:
        self.db.add(transition)
        await self.db.flush()
        return transition
