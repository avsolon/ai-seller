"""Website widget API (doc 13): session/messages/history/handoff/config.

All AI runs through the same SellerAgent core; the widget only sends and renders.
Session id = conversation id for MVP (history lives in PostgreSQL).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.orchestrator import process_message
from app.ai.agent.response import AgentResponse, build_response
from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.channels.service import MessageApplicationService
from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import (
    Conversation,
    ConversationStatus,
    Message,
    MessageType,
    SenderType,
)
from app.infrastructure.database.models.customer import Customer

router = APIRouter()
logger = get_logger(__name__)


class WidgetSessionRequest(BaseModel):
    external_session_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    page_url: Optional[str] = None


class WidgetMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    client_message_id: Optional[str] = None


class WidgetHandoffRequest(BaseModel):
    reason: str = "customer_requested"


class WidgetSessionResponse(BaseModel):
    session_id: str
    conversation_id: str
    customer_id: str
    shop_id: str
    config: dict


def _widget_config() -> dict:
    return {
        "enabled": True,
        "shop_name": settings.agent_name,
        "language": settings.default_language,
        "theme": "auto",
        "position": "right",
        "welcome": {
            "text": "Здравствуйте! Помогу подобрать линзы для вашего автомобиля."
        },
        "features": {
            "attachments": False,
            "quick_replies": True,
            "product_cards": True,
            "handoff": True,
        },
    }


def _serialize_message(message: Message) -> dict:
    return {
        "id": str(message.id),
        "role": "user" if message.sender_type == SenderType.CUSTOMER else "assistant",
        "text": message.text,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


async def _get_or_create_agent(db: AsyncSession, shop) -> Agent:
    result = await db.execute(select(Agent).where(Agent.shop_id == shop.id).limit(1))
    agent = result.scalar_one_or_none()
    if agent is None:
        agent = Agent(shop_id=shop.id, name="Default Agent", status="active")
        db.add(agent)
        await db.flush()
    return agent


async def _get_conversation(
    db: AsyncSession, session_id: UUID, shop_id: str
) -> Conversation:
    shop = await resolve_shop(db, shop_id)
    query = select(Conversation).where(Conversation.id == session_id)
    if shop is not None:
        query = query.where(Conversation.shop_id == shop.id)
    conversation = (await db.execute(query)).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return conversation


@router.post("/session", response_model=WidgetSessionResponse)
async def create_widget_session(
    request: WidgetSessionRequest,
    db: DatabaseSession,
    shop_id: ShopId,
) -> WidgetSessionResponse:
    """Create a customer + active conversation for the widget."""
    shop = await resolve_shop(db, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    customer = Customer(
        id=uuid4(),
        shop_id=shop.id,
        name=request.customer_name,
        phone=request.customer_phone,
    )
    db.add(customer)
    await db.flush()

    agent = await _get_or_create_agent(db, shop)
    conversation = Conversation(
        shop_id=shop.id,
        customer_id=customer.id,
        agent_id=agent.id,
        channel="web",
        external_session_id=request.external_session_id,
        status=ConversationStatus.ACTIVE,
        sales_state="NEW",
    )
    db.add(conversation)
    await db.flush()

    return WidgetSessionResponse(
        session_id=str(conversation.id),
        conversation_id=str(conversation.id),
        customer_id=str(customer.id),
        shop_id=str(shop.id),
        config=_widget_config(),
    )


@router.post("/session/{session_id}/messages")
async def send_widget_message(
    session_id: UUID,
    request: WidgetMessageRequest,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Process a widget message and return the structured AgentResponse."""
    conversation = await _get_conversation(db, session_id, shop_id)

    user_message = Message(
        conversation_id=conversation.id,
        sender_type=SenderType.CUSTOMER,
        message_type=MessageType.TEXT,
        channel="web",
        text=request.text,
        external_message_id=request.client_message_id,
        meta={},
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    try:
        result = await process_message(db, conversation, request.text)
        response: AgentResponse = build_response(result)
    except Exception as e:
        logger.warning(f"Agent failed for widget message: {e}")
        response = AgentResponse(
            text="Сейчас не удалось получить информацию. Давайте попробуем ещё раз."
        )

    agent_message = Message(
        conversation_id=conversation.id,
        sender_type=SenderType.AGENT,
        message_type=MessageType.TEXT,
        channel="web",
        text=response.text,
        meta={},
    )
    db.add(agent_message)
    await db.flush()
    await db.refresh(agent_message)
    conversation.last_message_at = agent_message.created_at
    await db.flush()

    return {
        "message_id": str(agent_message.id),
        "conversation_id": str(conversation.id),
        "response": response.to_dict(),
    }


@router.get("/session/{session_id}/messages")
async def widget_history(
    session_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Return conversation history for a widget session."""
    conversation = await _get_conversation(db, session_id, shop_id)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    messages = result.scalars().all()
    return {
        "conversation_id": str(conversation.id),
        "items": [_serialize_message(m) for m in messages],
        "page": page,
        "limit": limit,
    }


@router.post("/session/{session_id}/handoff")
async def widget_handoff(
    session_id: UUID,
    request: WidgetHandoffRequest,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Request a handoff to a human manager."""
    conversation = await _get_conversation(db, session_id, shop_id)
    service = MessageApplicationService()
    await service.request_handoff(db, conversation, reason=request.reason)
    return {"status": "created", "message": "Передал ваш вопрос менеджеру."}


@router.get("/config/{shop_id}")
async def widget_config(shop_id: str) -> dict:
    """Public widget configuration (safe, no secrets)."""
    return _widget_config()


@router.get("/config")
async def widget_config_default() -> dict:
    """Public widget configuration for the default shop."""
    return _widget_config()
