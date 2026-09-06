"""Lead routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, ShopId, resolve_shop
from app.api.schemas import LeadCreate
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.sales import Lead, LeadStatus
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _serialize_lead(lead: Lead) -> dict:
    """Serialize a lead to a plain dict."""
    return {
        "id": str(lead.id),
        "shop_id": str(lead.shop_id),
        "customer_id": str(lead.customer_id),
        "conversation_id": str(lead.conversation_id),
        "status": lead.status,
        "source": lead.source,
        "budget_min": float(lead.budget_min) if lead.budget_min is not None else None,
        "budget_max": float(lead.budget_max) if lead.budget_max is not None else None,
        "interest_level": lead.interest_level,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }


@router.post("/")
async def create_lead(
    request: LeadCreate,
    db: DatabaseSession,
    shop_id: ShopId,
) -> dict:
    """Create a lead from a conversation."""
    shop = await resolve_shop(db, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    conversation = await db.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    lead = Lead(
        shop_id=shop.id,
        customer_id=conversation.customer_id,
        conversation_id=conversation.id,
        status=LeadStatus.NEW,
        source=request.source or "ai_agent",
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        interest_level=request.interest_level,
    )
    db.add(lead)
    await db.flush()

    logger.info(f"Created lead {lead.id} from conversation {conversation.id}")
    return _serialize_lead(lead)


@router.get("/")
async def list_leads(
    db: DatabaseSession,
    shop_id: ShopId,
    lead_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
) -> dict:
    """List leads."""
    shop = await resolve_shop(db, shop_id)
    query = select(Lead)
    if shop is not None:
        query = query.where(Lead.shop_id == shop.id)
    if lead_status:
        query = query.where(Lead.status == lead_status)
    if customer_id:
        query = query.where(Lead.customer_id == customer_id)

    leads = (await db.execute(query)).scalars().all()
    return {
        "leads": [_serialize_lead(lead) for lead in leads],
        "total": len(leads),
    }
