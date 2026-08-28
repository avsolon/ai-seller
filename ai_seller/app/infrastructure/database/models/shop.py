"""Shop model."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.customer import Customer
    from app.infrastructure.database.models.product import Product
    from app.infrastructure.database.models.conversation import Conversation
    from app.infrastructure.database.models.agent import Agent
    from app.infrastructure.database.models.knowledge import KnowledgeDocument
    from app.infrastructure.database.models.sales_knowledge import SalesScenario, Objection


class ShopStatus(str):
    """Shop status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Shop(Base, UUIDMixin, TimestampMixin):
    """Shop entity - represents a tenant/magazin."""

    __tablename__ = "shops"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default=ShopStatus.ACTIVE, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), default="ru", nullable=False)

    # Relationships
    customers: Mapped[List["Customer"]] = relationship(
        "Customer", back_populates="shop", cascade="all, delete-orphan"
    )
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="shop", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="shop", cascade="all, delete-orphan"
    )
    agents: Mapped[List["Agent"]] = relationship(
        "Agent", back_populates="shop", cascade="all, delete-orphan"
    )
    knowledge_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument", back_populates="shop", cascade="all, delete-orphan"
    )
    sales_scenarios: Mapped[List["SalesScenario"]] = relationship(
        "SalesScenario", back_populates="shop", cascade="all, delete-orphan"
    )
    objections: Mapped[List["Objection"]] = relationship(
        "Objection", back_populates="shop", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Shop(id={self.id}, name={self.name}, slug={self.slug})>"
