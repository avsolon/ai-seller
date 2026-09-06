"""Website widget session routes."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.api.schemas import WidgetSessionCreate
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import (
    Channel,
    Conversation,
    ConversationStatus,
    SalesState,
)
from app.infrastructure.database.models.customer import Customer
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


async def _get_or_create_agent(db, shop) -> Agent:
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


@router.post("/session")
async def create_widget_session(
    request: WidgetSessionCreate,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Create a customer and an active conversation for the website widget."""
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
        channel=Channel.WEB,
        external_session_id=request.external_session_id,
        status=ConversationStatus.ACTIVE,
        sales_state=SalesState.NEW,
    )
    db.add(conversation)
    await db.flush()

    logger.info(
        f"Created widget session: customer={customer.id} conversation={conversation.id}"
    )
    return {
        "customer_id": str(customer.id),
        "conversation_id": str(conversation.id),
        "shop_id": str(shop.id),
    }


@router.get("/config")
async def widget_config() -> dict:
    """Public widget configuration (safe, no secrets)."""
    return {
        "shop_id": settings.shop_id,
        "language": settings.default_language,
        "agent_name": settings.agent_name,
        "tone": settings.agent_tone,
    }
