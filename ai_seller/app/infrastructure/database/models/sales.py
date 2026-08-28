"""Sales models."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.customer import Customer
    from app.infrastructure.database.models.conversation import Conversation
    from app.infrastructure.database.models.product import Product, ProductVariant


class RecommendationSource(str):
    """Recommendation source enum."""
    RULE = "rule"
    RAG = "rag"
    LLM = "llm"
    HYBRID = "hybrid"


class Recommendation(Base, UUIDMixin, TimestampMixin):
    """Product recommendation entity."""

    __tablename__ = "recommendations"

    conversation_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    variant_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), default=RecommendationSource.RULE, nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="recommendations"
    )
    customer: Mapped["Customer"] = relationship("Customer", back_populates="recommendations")
    product: Mapped["Product"] = relationship("Product", back_populates="recommendations")
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="recommendations", foreign_keys=[variant_id]
    )

    __table_args__ = (
        # Index for recommendations
        {"ix_recommendations_conversation": True},
        {"ix_recommendations_customer": True},
        {"ix_recommendations_product": True},
    )

    def __repr__(self) -> str:
        return f"<Recommendation(id={self.id}, product_id={self.product_id}, score={self.score})>"


class LeadStatus(str):
    """Lead status enum."""
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    IN_PROGRESS = "in_progress"
    CONVERTED = "converted"
    LOST = "lost"


class Lead(Base, UUIDMixin, TimestampMixin):
    """Lead entity - potential customer."""

    __tablename__ = "leads"

    shop_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=LeadStatus.NEW, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    budget_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    interest_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="leads")
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="leads"
    )

    __table_args__ = (
        # Index for leads
        {"ix_leads_shop": True},
        {"ix_leads_customer": True},
        {"ix_leads_status": True},
    )

    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, customer_id={self.customer_id}, status={self.status})>"


class OrderStatus(str):
    """Order status enum."""
    DRAFT = "draft"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Order(Base, UUIDMixin, TimestampMixin):
    """Order entity - customer order/request."""

    __tablename__ = "orders"

    shop_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=OrderStatus.DRAFT, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="orders"
    )
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Index for orders
        {"ix_orders_shop": True},
        {"ix_orders_customer": True},
        {"ix_orders_status": True},
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, customer_id={self.customer_id}, total={self.total_amount})>"


class OrderItem(Base, UUIDMixin, TimestampMixin):
    """Order item entity."""

    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    variant_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="order_items", foreign_keys=[variant_id]
    )

    __table_args__ = (
        # Index for order items
        {"ix_order_items_order": True},
        {"ix_order_items_product": True},
    )

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, product_id={self.product_id}, quantity={self.quantity})>"
