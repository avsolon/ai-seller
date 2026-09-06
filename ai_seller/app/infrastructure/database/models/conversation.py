"""Conversation models."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sqltext,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.customer import Customer
    from app.infrastructure.database.models.shop import Shop
    from app.infrastructure.database.models.agent import Agent
    from app.infrastructure.database.models.sales import Recommendation, Lead, Order
    from app.infrastructure.database.models.sales_state import SalesStateRecord
    from app.infrastructure.database.models.agent_run import AgentRun


class Channel(str):
    """Communication channel enum."""
    TELEGRAM = "telegram"
    WEB = "web"
    WHATSAPP = "whatsapp"
    VK = "vk"
    AVITO = "avito"
    MOBILE = "mobile"
    VOICE = "voice"


class ConversationStatus(str):
    """Conversation status enum."""
    ACTIVE = "active"
    CLOSED = "closed"
    WAITING_CUSTOMER = "waiting_customer"
    WAITING_MANAGER = "waiting_manager"
    HANDED_OFF = "handed_off"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class SalesState(str):
    """Sales state enum."""
    NEW = "new"
    GREETING = "greeting"
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    RECOMMENDATION = "recommendation"
    OBJECTION = "objection"
    NEGOTIATION = "negotiation"
    CLOSING = "closing"
    ORDER = "order"
    HUMAN_HANDOFF = "human_handoff"
    COMPLETED = "completed"


class SenderType(str):
    """Message sender type enum."""
    CUSTOMER = "customer"
    AGENT = "agent"
    MANAGER = "manager"
    SYSTEM = "system"
    TOOL = "tool"
    HUMAN = "human"


class MessageType(str):
    """Message type enum."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    BUTTON = "button"
    SYSTEM_EVENT = "system_event"


class Conversation(Base, UUIDMixin, TimestampMixin):
    """Conversation entity - main aggregate for AI sales interactions."""

    __tablename__ = "conversations"

    shop_id: Mapped[UUID] = mapped_column(
        ForeignKey("shops.id"), index=True, nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id"), index=True, nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id"), index=True, nullable=False
    )
    channel: Mapped[str] = mapped_column(String(30), default=Channel.WEB, nullable=False)
    external_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=ConversationStatus.ACTIVE, nullable=False
    )
    sales_state: Mapped[str] = mapped_column(
        String(50), default=SalesState.NEW, nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="conversations")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    sales_interactions: Mapped[List["SalesInteraction"]] = relationship(
        "SalesInteraction", back_populates="conversation", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="conversation", cascade="all, delete-orphan"
    )
    leads: Mapped[List["Lead"]] = relationship(
        "Lead", back_populates="conversation", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="conversation", cascade="all, delete-orphan"
    )
    sales_state_record: Mapped[Optional["SalesStateRecord"]] = relationship(
        "SalesStateRecord",
        back_populates="conversation",
        uselist=False,
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[List["AgentRun"]] = relationship(
        "AgentRun", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_shop_status", "shop_id", "status"),
        Index("ix_conversations_customer_created", "customer_id", "last_message_at"),
        Index("ix_conversations_last_message_at", "last_message_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, customer_id={self.customer_id}, status={self.status})>"


class Message(Base, UUIDMixin, TimestampMixin):
    """Message entity - individual message in a conversation."""

    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(30), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default=MessageType.TEXT, nullable=False)
    channel: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default={}, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    ai_data: Mapped[Optional["MessageAIData"]] = relationship(
        "MessageAIData", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )
    sales_interactions: Mapped[List["SalesInteraction"]] = relationship(
        "SalesInteraction", back_populates="message", foreign_keys="SalesInteraction.message_id"
    )

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index(
            "uq_message_external",
            "channel",
            "external_message_id",
            unique=True,
            postgresql_where=sqltext("external_message_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, sender={self.sender_type})>"


class MessageAIData(Base, UUIDMixin, TimestampMixin):
    """AI-specific metadata for messages."""

    __tablename__ = "message_ai_data"

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id"), unique=True, nullable=False, index=True
    )
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tokens_input: Mapped[Optional[int]] = mapped_column(nullable=True)
    tokens_output: Mapped[Optional[int]] = mapped_column(nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    rag_used: Mapped[Optional[bool]] = mapped_column(default=False, nullable=True)
    fallback_used: Mapped[Optional[bool]] = mapped_column(default=False, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default={}, nullable=True)

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="ai_data")

    def __repr__(self) -> str:
        return f"<MessageAIData(id={self.id}, message_id={self.message_id})>"


class SalesInteraction(Base, UUIDMixin, TimestampMixin):
    """Structured sales interaction for analytics."""

    __tablename__ = "sales_interactions"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sales_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default={}, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="sales_interactions")
    message: Mapped[Optional["Message"]] = relationship("Message", foreign_keys=[message_id])

    __table_args__ = (
        Index("ix_sales_interactions_conversation_created", "conversation_id", "created_at"),
        Index("ix_sales_interactions_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<SalesInteraction(id={self.id}, type={self.type}, conversation_id={self.conversation_id})>"
