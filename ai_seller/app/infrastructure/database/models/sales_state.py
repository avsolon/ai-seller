"""SalesState persistent record (doc 8: SalesState entity with optimistic lock).

The nested value objects (vehicle / need / purchase / objections / missing_slots)
are stored as JSONB. stage/intent/emotion/customer_type are typed columns so the
state is filterable and queryable. `version` protects against conflicting updates.
"""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.conversation import Conversation
    from app.infrastructure.database.models.product import Product


class SalesStateRecord(Base, UUIDMixin, TimestampMixin):
    """Persistent snapshot of the current SalesState of a conversation."""

    __tablename__ = "sales_states"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), unique=True, nullable=False
    )
    stage: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vehicle: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    need: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    purchase: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    objections: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    missing_slots: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    selected_product_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    purchase_intent_score: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 3), default=0, nullable=True
    )
    handoff_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="sales_state_record"
    )
    selected_product: Mapped[Optional["Product"]] = relationship(
        "Product", foreign_keys=[selected_product_id]
    )

    __table_args__ = (
        Index("ix_sales_states_stage", "stage"),
        Index("ix_sales_states_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SalesStateRecord(id={self.id}, conversation_id={self.conversation_id}, stage={self.stage})>"


class StateTransition(Base, UUIDMixin, TimestampMixin):
    """History of funnel transitions for a conversation (doc 9: analytics)."""

    __tablename__ = "state_transitions"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    from_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", foreign_keys=[conversation_id]
    )

    __table_args__ = (
        Index("ix_state_transitions_conversation_created", "conversation_id", "created_at"),
        Index("ix_state_transitions_to_stage", "to_stage"),
    )

    def __repr__(self) -> str:
        return f"<StateTransition(id={self.id}, {self.from_stage}->{self.to_stage})>"
