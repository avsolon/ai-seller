"""Conversation routes."""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DatabaseSession, AppSettings, ShopId
from app.infrastructure.database.models.conversation import (
    Conversation,
    ConversationStatus,
    Channel,
    SalesState,
)
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.agent import Agent
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ConversationCreateRequest:
    """Request model for creating a conversation."""
    customer_id: UUID
    channel: str = Channel.WEB
    external_session_id: Optional[str] = None
    initial_message: Optional[str] = None


class ConversationResponse:
    """Response model for conversation."""
    id: UUID
    shop_id: UUID
    customer_id: UUID
    agent_id: UUID
    channel: str
    status: str
    sales_state: str
    summary: Optional[str]
    created_at: str
    last_message_at: Optional[str]


class ConversationListResponse:
    """Response model for conversation list."""
    conversations: List[ConversationResponse]
    total: int
    page: int
    page_size: int


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreateRequest,
    db: DatabaseSession,
    settings: AppSettings,
    shop_id: ShopId,
) -> ConversationResponse:
    """Create a new conversation."""
    # Get or create default agent for the shop
    result = await db.execute(
        select(Agent).where(Agent.shop_id == shop_id).limit(1)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        # Create default agent
        agent = Agent(
            shop_id=shop_id,
            name="Default Agent",
            description="Default AI Seller Agent",
            status="active",
        )
        db.add(agent)
        await db.flush()
    
    # Create conversation
    conversation = Conversation(
        shop_id=shop_id,
        customer_id=request.customer_id,
        agent_id=agent.id,
        channel=request.channel,
        external_session_id=request.external_session_id,
        status=ConversationStatus.ACTIVE,
        sales_state=SalesState.NEW,
    )
    
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    
    logger.info(f"Created conversation {conversation.id} for customer {request.customer_id}")
    
    return ConversationResponse(
        id=conversation.id,
        shop_id=conversation.shop_id,
        customer_id=conversation.customer_id,
        agent_id=conversation.agent_id,
        channel=conversation.channel,
        status=conversation.status,
        sales_state=conversation.sales_state,
        summary=conversation.summary,
        created_at=conversation.created_at.isoformat(),
        last_message_at=conversation.last_message_at.isoformat() if conversation.last_message_at else None,
    )


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    db: DatabaseSession,
    shop_id: ShopId,
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
) -> ConversationListResponse:
    """List conversations."""
    query = select(Conversation).where(Conversation.shop_id == shop_id)
    
    if customer_id:
        query = query.where(Conversation.customer_id == customer_id)
    
    if status:
        query = query.where(Conversation.status == status)
    
    # Count total
    count_result = await db.execute(select([func.count()]).select_from(query.subquery()))
    total = count_result.scalar_one()
    
    # Paginate
    query = query.order_by(desc(Conversation.last_message_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    return ConversationListResponse(
        conversations=[
            ConversationResponse(
                id=c.id,
                shop_id=c.shop_id,
                customer_id=c.customer_id,
                agent_id=c.agent_id,
                channel=c.channel,
                status=c.status,
                sales_state=c.sales_state,
                summary=c.summary,
                created_at=c.created_at.isoformat(),
                last_message_at=c.last_message_at.isoformat() if c.last_message_at else None,
            )
            for c in conversations
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
) -> ConversationResponse:
    """Get a specific conversation."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.shop_id == shop_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    return ConversationResponse(
        id=conversation.id,
        shop_id=conversation.shop_id,
        customer_id=conversation.customer_id,
        agent_id=conversation.agent_id,
        channel=conversation.channel,
        status=conversation.status,
        sales_state=conversation.sales_state,
        summary=conversation.summary,
        created_at=conversation.created_at.isoformat(),
        last_message_at=conversation.last_message_at.isoformat() if conversation.last_message_at else None,
    )


@router.patch("/{conversation_id}/status", response_model=ConversationResponse)
async def update_conversation_status(
    conversation_id: UUID,
    status: str,
    db: DatabaseSession,
    shop_id: ShopId,
) -> ConversationResponse:
    """Update conversation status."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.shop_id == shop_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    conversation.status = status
    await db.flush()
    await db.refresh(conversation)
    
    logger.info(f"Updated conversation {conversation_id} status to {status}")
    
    return ConversationResponse(
        id=conversation.id,
        shop_id=conversation.shop_id,
        customer_id=conversation.customer_id,
        agent_id=conversation.agent_id,
        channel=conversation.channel,
        status=conversation.status,
        sales_state=conversation.sales_state,
        summary=conversation.summary,
        created_at=conversation.created_at.isoformat(),
        last_message_at=conversation.last_message_at.isoformat() if conversation.last_message_at else None,
    )
