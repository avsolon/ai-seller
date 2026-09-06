"""Request and response schemas (Pydantic v2) for the AI Seller API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class ConversationCreate(BaseModel):
    customer_id: UUID
    channel: str = "web"
    external_session_id: Optional[str] = None
    initial_message: Optional[str] = None


class ConversationStatusUpdate(BaseModel):
    status: str


class MessageSend(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    sender_type: str = "customer"
    external_message_id: Optional[str] = None


class LeadCreate(BaseModel):
    conversation_id: UUID
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    interest_level: Optional[int] = None
    source: Optional[str] = None


class OrderItemCreate(BaseModel):
    product_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int = Field(default=1, ge=1)


class OrderCreate(BaseModel):
    conversation_id: UUID
    items: List[OrderItemCreate] = Field(min_length=1)
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_city: Optional[str] = None


class RecommendationRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    category: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    limit: int = 3


class WidgetSessionCreate(BaseModel):
    external_session_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    page_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Responses (ORM -> dict via from_attributes)
# ---------------------------------------------------------------------------

_response_config = ConfigDict(from_attributes=True)


class ConversationOut(BaseModel):
    model_config = _response_config

    id: UUID
    shop_id: UUID
    customer_id: UUID
    agent_id: UUID
    channel: str
    external_session_id: Optional[str] = None
    status: str
    sales_state: str
    summary: Optional[str] = None
    created_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class CustomerOut(BaseModel):
    model_config = _response_config

    id: UUID
    shop_id: UUID
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None
    created_at: Optional[datetime] = None


class MessageOut(BaseModel):
    model_config = _response_config

    id: UUID
    conversation_id: UUID
    sender_type: str
    message_type: str
    text: str
    external_message_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ProductOut(BaseModel):
    model_config = _response_config

    id: UUID
    shop_id: UUID
    sku: str
    name: str
    slug: str
    brand: str
    category: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str
    stock_quantity: int
    specifications: Optional[dict] = None
    is_active: bool


class LeadOut(BaseModel):
    model_config = _response_config

    id: UUID
    shop_id: UUID
    customer_id: UUID
    conversation_id: UUID
    status: str
    source: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    interest_level: Optional[int] = None
    score: Optional[float] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class OrderItemOut(BaseModel):
    model_config = _response_config

    id: UUID
    order_id: UUID
    product_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int
    unit_price: float
    total_price: float


class OrderOut(BaseModel):
    model_config = _response_config

    id: UUID
    shop_id: UUID
    customer_id: UUID
    conversation_id: UUID
    status: str
    total_amount: float
    currency: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_city: Optional[str] = None
    created_at: Optional[datetime] = None
    items: List[OrderItemOut] = Field(default_factory=list)
