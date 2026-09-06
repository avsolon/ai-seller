"""Repository interfaces (ports).

MVP note: repositories return SQLAlchemy ORM models which currently act as the
domain entities. Keeping the protocol separate lets us later swap the persistence
layer (PostgreSQL -> anything) without touching the agent/use-case code.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID

from app.infrastructure.database.models.conversation import Conversation, Message
from app.infrastructure.database.models.customer import Customer, CustomerExternalID
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.sales_state import SalesStateRecord, StateTransition


@runtime_checkable
class CustomerRepository(Protocol):
    async def get(self, customer_id: UUID) -> Optional[Customer]: ...

    async def find_by_external(self, channel: str, external_id: str) -> Optional[Customer]: ...

    async def create(self, customer: Customer) -> Customer: ...

    async def add_external_id(self, customer_id: UUID, channel: str, external_id: str) -> CustomerExternalID: ...


@runtime_checkable
class ConversationRepository(Protocol):
    async def get(self, conversation_id: UUID) -> Optional[Conversation]: ...

    async def get_active_by_customer(
        self, customer_id: UUID, channel: Optional[str] = None
    ) -> Optional[Conversation]: ...

    async def create(self, conversation: Conversation) -> Conversation: ...

    async def update_status(self, conversation: Conversation, status: str) -> Conversation: ...

    async def touch(self, conversation: Conversation) -> None: ...


@runtime_checkable
class MessageRepository(Protocol):
    async def add(self, message: Message) -> Message: ...

    async def list_by_conversation(
        self, conversation_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[Message]: ...


@runtime_checkable
class ProductRepository(Protocol):
    async def get(self, product_id: UUID) -> Optional[Product]: ...

    async def get_by_sku(self, shop_id: UUID, sku: str) -> Optional[Product]: ...

    async def search(
        self,
        shop_id: Optional[UUID] = None,
        search: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Product]: ...


@runtime_checkable
class SalesStateRepository(Protocol):
    async def get_by_conversation(self, conversation_id: UUID) -> Optional[SalesStateRecord]: ...

    async def upsert(self, state: SalesStateRecord) -> SalesStateRecord: ...

    async def add_transition(self, transition: StateTransition) -> StateTransition: ...
