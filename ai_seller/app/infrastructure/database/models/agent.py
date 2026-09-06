"""Agent models."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.shop import Shop
    from app.infrastructure.database.models.conversation import Conversation


class AgentStatus(str):
    """Agent status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"


class Agent(Base, UUIDMixin, TimestampMixin):
    """AI Agent entity."""

    __tablename__ = "agents"

    shop_id: Mapped[UUID] = mapped_column(
        ForeignKey("shops.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=AgentStatus.ACTIVE, nullable=False)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="agents")
    configuration: Mapped[Optional["AgentConfiguration"]] = relationship(
        "AgentConfiguration", back_populates="agent", uselist=False, cascade="all, delete-orphan"
    )
    prompt_versions: Mapped[List["PromptVersion"]] = relationship(
        "PromptVersion", back_populates="agent", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="agent", foreign_keys="Conversation.agent_id"
    )

    __table_args__ = (
        UniqueConstraint("shop_id", "name", name="uq_agents_shop_name"),
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name}, shop_id={self.shop_id})>"


class AgentConfiguration(Base, UUIDMixin, TimestampMixin):
    """AI Agent configuration."""

    __tablename__ = "agent_configurations"

    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id"), unique=True, nullable=False, index=True
    )
    llm_provider: Mapped[str] = mapped_column(String(50), default="ollama", nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sales_rag_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rag_top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="ru", nullable=False)
    tone: Mapped[str] = mapped_column(String(50), default="professional", nullable=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="configuration")

    def __repr__(self) -> str:
        return f"<AgentConfiguration(id={self.id}, agent_id={self.agent_id})>"


class PromptVersion(Base, UUIDMixin, TimestampMixin):
    """Prompt version history."""

    __tablename__ = "prompt_versions"

    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    sales_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personality_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="prompt_versions")

    __table_args__ = (
        Index("ix_prompt_versions_agent_active", "agent_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<PromptVersion(id={self.id}, version={self.version}, active={self.is_active})>"
