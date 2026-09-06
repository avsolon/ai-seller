"""Feedback model (doc 9): ratings and labels on agent responses."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.conversation import Conversation, Message
    from app.infrastructure.database.models.agent_run import AgentRun


class Feedback(Base, UUIDMixin, TimestampMixin):
    """User/manager feedback on a specific agent reply."""

    __tablename__ = "feedback"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    agent_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", foreign_keys=[conversation_id]
    )
    message: Mapped[Optional["Message"]] = relationship(
        "Message", foreign_keys=[message_id]
    )
    agent_run: Mapped[Optional["AgentRun"]] = relationship(
        "AgentRun", foreign_keys=[agent_run_id]
    )

    __table_args__ = (
        Index("ix_feedback_conversation_created", "conversation_id", "created_at"),
        Index("ix_feedback_label", "label"),
    )

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, conversation_id={self.conversation_id}, label={self.label})>"
