"""Customer models."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.shop import Shop
    from app.infrastructure.database.models.conversation import Conversation
    from app.infrastructure.database.models.sales import Recommendation, Lead, Order
    from app.infrastructure.database.models.product import Vehicle


class Customer(Base, UUIDMixin, TimestampMixin):
    """Customer entity."""

    __tablename__ = "customers"

    shop_id: Mapped[UUID] = mapped_column(
        ForeignKey("shops.id"), index=True, nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="customers")
    profile: Mapped[Optional["CustomerProfile"]] = relationship(
        "CustomerProfile", back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )
    external_ids: Mapped[List["CustomerExternalID"]] = relationship(
        "CustomerExternalID", back_populates="customer", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="customer", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="customer", cascade="all, delete-orphan"
    )
    leads: Mapped[List["Lead"]] = relationship(
        "Lead", back_populates="customer", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="customer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("shop_id", "telegram_user_id", name="uq_customers_shop_telegram"),
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name={self.name}, telegram_user_id={self.telegram_user_id})>"


class CustomerExternalID(Base, UUIDMixin, TimestampMixin):
    """Channel-specific identifier of a customer (doc 9: normalized external ids)."""

    __tablename__ = "customer_external_ids"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="external_ids")

    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_customer_external_channel_id"),
    )

    def __repr__(self) -> str:
        return f"<CustomerExternalID(id={self.id}, channel={self.channel})>"


class CustomerProfile(Base, UUIDMixin, TimestampMixin):
    """Customer profile with additional information learned by AI."""

    __tablename__ = "customer_profiles"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id"), unique=True, nullable=False, index=True
    )
    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vehicles.id"), nullable=True
    )
    budget_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    customer_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)
    facts: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="profile")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[vehicle_id])

    def __repr__(self) -> str:
        return f"<CustomerProfile(id={self.id}, customer_id={self.customer_id})>"
