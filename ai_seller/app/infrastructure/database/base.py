"""Base database models and utilities."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, index=True, unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TimestampMixin:
    """Mixin for timestamp fields."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, index=True, unique=True, nullable=False
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        """Mark entity as deleted."""
        self.is_active = False
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore soft-deleted entity."""
        self.is_active = True
        self.deleted_at = None


class ShopBoundMixin:
    """Mixin for entities bound to a shop."""

    shop_id: Mapped[UUID] = mapped_column(
        index=True, nullable=False
    )
