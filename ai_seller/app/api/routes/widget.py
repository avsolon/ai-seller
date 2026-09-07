"""Website widget API (doc 13): session/messages/events/history/handoff/config.

Session id = conversation id for MVP. Message replies are also published to an
SSE event stream (open GET /events before posting a message).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.orchestrator import process_message
from app.ai.agent.response import AgentResponse, build_response
from app.api.widget_events import next_event, push_event, split_text
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

_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "widget"

# In-memory sliding-window rate limiting (session) — replace with Redis in prod
_RATE: Dict[str, List[float]] = {}


def _check_rate(key: str, limit: int, window: float) -> bool:
    now = time.monotonic()
    hits = [t for t in _RATE.get(key, []) if now - t < window]
    if len(hits) >= limit:
        _RATE[key] = hits
        return False
    hits.append(now)
    _RATE[key] = hits
    return True


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
            "attachments": True,
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


async def _get_conversation(db: AsyncSession, session_id: UUID, shop_id: str) -> Conversation:
    shop = await resolve_shop(db, shop_id)
    query = select(Conversation).where(Conversation.id == session_id)
    if shop is not None:
        query = query.where(Conversation.shop_id == shop.id)
    conversation = (await db.execute(query)).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return conversation


async def _publish_response(session_id: str, agent_message: Message, response: AgentResponse) -> None:
    """Publish typed SSE events for a finished widget turn."""
    session = str(session_id)
    await push_event(session, "message_start", {"message_id": str(agent_message.id)})
    for chunk in split_text(response.text):
        await push_event(session, "message_delta", {"text": chunk})
    for product in response.products:
        await push_event(session, "product_card", {"product": product})
    if response.quick_replies:
        await push_event(session, "quick_replies", {"items": response.quick_replies})
    if response.handoff:
        await push_event(session, "handoff", {"status": "created", "reason": "agent_handoff"})
    await push_event(
        session,
        "message_end",
        {
            "message_id": str(agent_message.id),
            "stage": response.stage,
            "handoff": response.handoff,
        },
    )


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
    """Process a widget message and return/publish the structured AgentResponse."""
    if not _check_rate(f"session:{session_id}", 30, 60):
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED"})

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

    await _publish_response(session_id, agent_message, response)

    return {
        "message_id": str(agent_message.id),
        "conversation_id": str(conversation.id),
        "response": response.to_dict(),
    }


@router.get("/session/{session_id}/events")
async def widget_events(
    session_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
) -> StreamingResponse:
    """SSE stream: open before posting a message to receive typing/deltas/end."""
    await _get_conversation(db, session_id, shop_id)
    session = str(session_id)

    async def event_stream():
        yield "retry: 15000\n\n"
        while True:
            item = await next_event(session, timeout=15.0)
            if item is None:
                yield ": keep-alive\n\n"
                continue
            event, data = item
            yield f"event: {event}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    await push_event(
        str(session_id),
        "handoff",
        {"status": "created", "reason": request.reason},
    )
    return {"status": "created", "message": "Передал ваш вопрос менеджеру."}


@router.post("/session/{session_id}/attachments")
async def widget_upload_attachment(
    session_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
    file: UploadFile = File(...),
) -> dict:
    """Store an attachment (photo of the headlight, etc.)."""
    await _get_conversation(db, session_id, shop_id)

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix or ""
    attachment_id = uuid4()
    target = _UPLOAD_DIR / f"{attachment_id}{ext}"
    content = await file.read()
    target.write_bytes(content)

    return {
        "attachment_id": str(attachment_id),
        "type": "image" if file.content_type and file.content_type.startswith("image/") else "document",
        "status": "uploaded",
        "size_bytes": len(content),
    }


@router.get("/config/{shop_id}")
async def widget_config(shop_id: str) -> dict:
    """Public widget configuration (safe, no secrets)."""
    return _widget_config()


@router.get("/config")
async def widget_config_default() -> dict:
    """Public widget configuration for the default shop."""
    return _widget_config()
