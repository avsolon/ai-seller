"""ManagerTask model (doc 12): handoff queue entry for a human manager."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.conversation import Conversation


class ManagerTaskStatus(str):
    OPEN = "open"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ManagerTask(Base, UUIDMixin, TimestampMixin):
    """Task for a human manager created when the agent requests a handoff."""

    __tablename__ = "manager_tasks"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), default="handoff", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ManagerTaskStatus.OPEN, nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", foreign_keys=[conversation_id]
    )

    __table_args__ = (
        Index("ix_manager_tasks_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ManagerTask(id={self.id}, conversation_id={self.conversation_id}, status={self.status})>"
