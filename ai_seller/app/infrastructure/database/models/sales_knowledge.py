"""Sales knowledge models."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.shop import Shop


class SalesScenario(Base, UUIDMixin, TimestampMixin):
    """Sales scenario entity."""

    __tablename__ = "sales_scenarios"

    shop_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sales_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="sales_scenarios")
    dialogues: Mapped[List["SalesDialogue"]] = relationship(
        "SalesDialogue", back_populates="scenario", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Index for sales scenarios
        {"ix_sales_scenarios_shop": True},
        {"ix_sales_scenarios_intent": True},
        {"ix_sales_scenarios_stage": True},
    )

    def __repr__(self) -> str:
        return f"<SalesScenario(id={self.id}, name={self.name}, intent={self.intent})>"


class CustomerType(str):
    """Customer type enum."""
    NEWBIE = "newbie"
    ENTHUSIAST = "enthusiast"
    PROFESSIONAL = "professional"
    BUDGET = "budget"
    PREMIUM = "premium"
    SKEPTICAL = "skeptical"
    REPEAT_CUSTOMER = "repeat_customer"


class Emotion(str):
    """Emotion enum."""
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    INTERESTED = "interested"
    SKEPTICAL = "skeptical"
    CONFUSED = "confused"
    IMPATIENT = "impatient"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    READY_TO_BUY = "ready_to_buy"
    ANGRY = "angry"


class SalesGoal(str):
    """Sales goal enum."""
    DISCOVER_NEED = "discover_need"
    QUALIFY = "qualify"
    RECOMMEND = "recommend"
    JUSTIFY_PRICE = "justify_price"
    HANDLE_OBJECTION = "handle_objection"
    UPSELL = "upsell"
    CROSS_SELL = "cross_sell"
    CLOSE = "close"
    HANDOFF = "handoff"


class SalesDialogue(Base, UUIDMixin, TimestampMixin):
    """Sales dialogue entity - example conversation for Sales RAG."""

    __tablename__ = "sales_dialogues"

    scenario_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    shop_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sales_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dialogue: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)

    # Relationships
    scenario: Mapped["SalesScenario"] = relationship("SalesScenario", back_populates="dialogues")
    shop: Mapped["Shop"] = relationship("Shop")
    objections: Mapped[List["Objection"]] = relationship(
        "Objection", secondary="sales_dialogue_objections", back_populates="dialogues"
    )

    __table_args__ = (
        # Index for sales dialogues
        {"ix_sales_dialogues_scenario": True},
        {"ix_sales_dialogues_shop": True},
        {"ix_sales_dialogues_intent": True},
        {"ix_sales_dialogues_stage": True},
    )

    def __repr__(self) -> str:
        return f"<SalesDialogue(id={self.id}, title={self.title}, scenario_id={self.scenario_id})>"


class Objection(Base, UUIDMixin, TimestampMixin):
    """Objection entity - common customer objections."""

    __tablename__ = "objections"

    shop_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="objections")
    dialogues: Mapped[List["SalesDialogue"]] = relationship(
        "SalesDialogue", secondary="sales_dialogue_objections", back_populates="objections"
    )

    __table_args__ = (
        # Unique constraint for objection code per shop
        {"ix_objections_shop_code": True},
    )

    def __repr__(self) -> str:
        return f"<Objection(id={self.id}, code={self.code}, name={self.name})>"


# Association table for many-to-many relationship between SalesDialogue and Objection
sales_dialogue_objections = (
    "sales_dialogue_objections",
    Base.metadata,
    Mapped[Any],
    {
        "columns": [
            mapped_column("sales_dialogue_id", UUID, nullable=False),
            mapped_column("objection_id", UUID, nullable=False),
        ],
        "primary_key": ("sales_dialogue_id", "objection_id"),
    },
)
