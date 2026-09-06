"""Conversation routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.api.schemas import ConversationCreate, ConversationOut, ConversationStatusUpdate
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import (
    Conversation,
    ConversationStatus,
    Message,
    MessageType,
    SalesState,
    SenderType,
)
from app.infrastructure.database.models.customer import Customer
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _dump(conversation: Conversation) -> dict:
    """Serialize a conversation ORM object to a JSON-safe dict via the schema."""
    return ConversationOut.model_validate(conversation).model_dump(mode="json")


async def _get_agent(db: AsyncSession, shop) -> Agent:
    """Get or create the default agent for the shop."""
    result = await db.execute(select(Agent).where(Agent.shop_id == shop.id).limit(1))
    agent = result.scalar_one_or_none()
    if agent is None:
        agent = Agent(
            shop_id=shop.id,
            name="Default Agent",
            description="Default AI Seller Agent",
            status="active",
        )
        db.add(agent)
        await db.flush()
    return agent


@router.post("/", response_model=ConversationOut)
async def create_conversation(
    request: ConversationCreate,
    db: DatabaseSession,
    shop_id: ShopId,
) -> Conversation:
    """Create a new conversation."""
    shop = await resolve_shop(db, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    customer = await db.get(Customer, request.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    agent = await _get_agent(db, shop)

    conversation = Conversation(
        shop_id=shop.id,
        customer_id=customer.id,
        agent_id=agent.id,
        channel=request.channel,
        external_session_id=request.external_session_id,
        status=ConversationStatus.ACTIVE,
        sales_state=SalesState.NEW,
    )
    db.add(conversation)
    await db.flush()

    logger.info(f"Created conversation {conversation.id} for customer {customer.id}")

    # Optionally store the initial customer message
    if request.initial_message:
        db.add(
            Message(
                conversation_id=conversation.id,
                sender_type=SenderType.CUSTOMER,
                message_type=MessageType.TEXT,
                channel=request.channel,
                text=request.initial_message,
                meta={},
            )
        )
        await db.flush()

    return conversation


@router.get("/")
async def list_conversations(
    db: DatabaseSession,
    shop_id: ShopId,
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    conv_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
) -> dict:
    """List conversations."""
    shop = await resolve_shop(db, shop_id)
    query = select(Conversation)
    if shop is not None:
        query = query.where(Conversation.shop_id == shop.id)

    if customer_id:
        query = query.where(Conversation.customer_id == customer_id)

    if conv_status:
        query = query.where(Conversation.status == conv_status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()

    query = (
        query.order_by(desc(Conversation.last_message_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = (await db.execute(query)).scalars().all()

    return {
        "conversations": [_dump(c) for c in conversations],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
) -> Conversation:
    """Get a specific conversation."""
    shop = await resolve_shop(db, shop_id)
    query = select(Conversation).where(Conversation.id == conversation_id)
    if shop is not None:
        query = query.where(Conversation.shop_id == shop.id)

    conversation = (await db.execute(query)).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


@router.patch("/{conversation_id}/status", response_model=ConversationOut)
async def update_conversation_status(
    conversation_id: UUID,
    request: ConversationStatusUpdate,
    db: DatabaseSession,
    shop_id: ShopId,
) -> Conversation:
    """Update conversation status."""
    shop = await resolve_shop(db, shop_id)
    query = select(Conversation).where(Conversation.id == conversation_id)
    if shop is not None:
        query = query.where(Conversation.shop_id == shop.id)

    conversation = (await db.execute(query)).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    conversation.status = request.status
    await db.flush()

    logger.info(f"Updated conversation {conversation_id} status to {request.status}")
    return conversation
