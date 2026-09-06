"""AgentRun model (doc 8): audit trail of a single SellerAgent processing step.

Answers "why did the agent answer this way": stores state before/after,
retrieved chunks, tool calls, response and latency.
"""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.conversation import Conversation, Message


class AgentRun(Base, UUIDMixin, TimestampMixin):
    """One processing run of the SellerAgent."""

    __tablename__ = "agent_runs"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state_before: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    state_after: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    retrieved_chunks: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="agent_runs"
    )
    message: Mapped[Optional["Message"]] = relationship(
        "Message", foreign_keys=[message_id]
    )
    tool_calls: Mapped[List["ToolCall"]] = relationship(
        "ToolCall", back_populates="agent_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_agent_runs_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AgentRun(id={self.id}, conversation_id={self.conversation_id})>"


class ToolCall(Base, UUIDMixin, TimestampMixin):
    """A tool invocation made during an AgentRun (doc 9: separate table)."""

    __tablename__ = "tool_calls"

    agent_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    agent_run: Mapped["AgentRun"] = relationship(
        "AgentRun", back_populates="tool_calls"
    )

    def __repr__(self) -> str:
        return f"<ToolCall(id={self.id}, tool={self.tool_name})>"
