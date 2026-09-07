"""Message routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.api.schemas import MessageSend
from app.infrastructure.database.models.conversation import (
    Conversation,
    ConversationStatus,
    Message,
    MessageType,
    SenderType,
)
from app.infrastructure.database.models.product import Product
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _serialize_message(message: Message) -> dict:
    """Serialize a message to a plain dict."""
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender_type": message.sender_type,
        "message_type": message.message_type,
        "text": message.text,
        "external_message_id": message.external_message_id,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


async def _get_conversation(
    db: AsyncSession, conversation_id: UUID, shop_identifier: str
) -> Conversation:
    """Fetch a conversation scoped to the current shop."""
    shop = await resolve_shop(db, shop_identifier)
    query = select(Conversation).where(Conversation.id == conversation_id)
    if shop is not None:
        query = query.where(Conversation.shop_id == shop.id)
    conversation = (await db.execute(query)).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


async def _try_agent_reply(
    db: AsyncSession, conversation: Conversation, user_message: str
) -> str:
    """Try to generate an AI reply. Falls back to a polite acknowledgement."""
    fallback = (
        "Спасибо за сообщение! Я передал ваш вопрос. "
        "Менеджер свяжется с вами в ближайшее время."
    )
    try:
        # Lazy import: the AI stack (qdrant/redis/llm) is optional for the skeleton.
        from app.ai.agent.orchestrator import process_message

        product_result = await db.execute(
            select(Product).where(
                Product.shop_id == conversation.shop_id,
                Product.is_active.is_(True),
            )
        )
        products = list(product_result.scalars().all())

        result = await process_message(
            db=db,
            conversation=conversation,
            text=user_message,
            products=products,
        )
        text = (result.get("reply") or "").strip()
        return text if text else fallback
    except Exception as e:
        logger.warning(f"AI agent unavailable, using fallback reply: {e}")
        return fallback


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: UUID,
    db: DatabaseSession,
    shop_id: ShopId,
    limit: int = Query(50, ge=1, le=200, description="Number of messages"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict:
    """Get message history for a conversation."""
    conversation = await _get_conversation(db, conversation_id, shop_id)

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .offset(offset)
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()

    return {
        "conversation_id": str(conversation.id),
        "total": len(messages),
        "messages": [_serialize_message(m) for m in messages],
    }


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    request: MessageSend,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Send a customer message and return the AI reply."""
    conversation = await _get_conversation(db, conversation_id, shop_id)

    # Persist the customer message first so the agent can read full history
    user_message = Message(
        conversation_id=conversation.id,
        sender_type=SenderType.CUSTOMER,
        message_type=MessageType.TEXT,
        text=request.text,
        external_message_id=request.external_message_id,
        meta={},
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(conversation)

    reply_text = await _try_agent_reply(db, conversation, request.text)

    agent_message = Message(
        conversation_id=conversation.id,
        sender_type=SenderType.AGENT,
        message_type=MessageType.TEXT,
        text=reply_text,
        meta={},
    )
    db.add(agent_message)
    await db.flush()
    await db.refresh(agent_message)
    conversation.last_message_at = agent_message.created_at
    await db.flush()

    return {
        "conversation_id": str(conversation.id),
        "user_message": _serialize_message(user_message),
        "agent_message": _serialize_message(agent_message),
        "sales_state": conversation.sales_state,
        "handoff": conversation.status
        in (ConversationStatus.WAITING_MANAGER, ConversationStatus.HANDED_OFF),
    }
