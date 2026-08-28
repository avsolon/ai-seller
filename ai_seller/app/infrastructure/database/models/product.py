"""Product models."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.shop import Shop
    from app.infrastructure.database.models.conversation import Conversation
    from app.infrastructure.database.models.sales import Recommendation, Order, OrderItem


class Product(Base, UUIDMixin, TimestampMixin):
    """Product entity."""

    __tablename__ = "products"

    shop_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    specifications: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="products")
    variants: Mapped[List["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )
    compatibilities: Mapped[List["Compatibility"]] = relationship(
        "Compatibility", back_populates="product", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="product", foreign_keys="Recommendation.product_id"
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="product", foreign_keys="OrderItem.product_id"
    )

    __table_args__ = (
        # Unique constraint for SKU per shop
        {"ix_products_shop_sku": True},
        # Unique constraint for slug per shop
        {"ix_products_shop_slug": True},
        # Index for active products
        {"ix_products_active": True},
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku}, name={self.name})>"


class ProductVariant(Base, UUIDMixin, TimestampMixin):
    """Product variant entity."""

    __tablename__ = "product_variants"

    product_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    compatibilities: Mapped[List["Compatibility"]] = relationship(
        "Compatibility", back_populates="variant", foreign_keys="Compatibility.variant_id"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="variant", foreign_keys="Recommendation.variant_id"
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="variant", foreign_keys="OrderItem.variant_id"
    )

    __table_args__ = (
        # Unique constraint for SKU per product
        {"ix_product_variants_product_sku": True},
    )

    def __repr__(self) -> str:
        return f"<ProductVariant(id={self.id}, product_id={self.product_id}, sku={self.sku})>"


class Vehicle(Base, UUIDMixin, TimestampMixin):
    """Vehicle entity."""

    __tablename__ = "vehicles"

    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    generation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    compatibilities: Mapped[List["Compatibility"]] = relationship(
        "Compatibility", back_populates="vehicle", cascade="all, delete-orphan"
    )
    customer_profiles: Mapped[List["CustomerProfile"]] = relationship(
        "CustomerProfile", back_populates="vehicle", foreign_keys="CustomerProfile.vehicle_id"
    )

    __table_args__ = (
        # Unique constraint for vehicle
        {"ix_vehicles_brand_model": True},
    )

    def __repr__(self) -> str:
        return f"<Vehicle(id={self.id}, brand={self.brand}, model={self.model})>"


class CompatibilityType(str):
    """Compatibility type enum."""
    DIRECT = "direct"
    ADAPTER_REQUIRED = "adapter_required"
    MODIFICATION_REQUIRED = "modification_required"
    NOT_RECOMMENDED = "not_recommended"


class Compatibility(Base, UUIDMixin, TimestampMixin):
    """Compatibility entity - defines which products work with which vehicles."""

    __tablename__ = "compatibilities"

    product_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    vehicle_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    variant_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    type: Mapped[str] = mapped_column(String(50), default=CompatibilityType.DIRECT, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="compatibilities")
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="compatibilities", foreign_keys=[variant_id]
    )
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="compatibilities")

    __table_args__ = (
        # Unique constraint for product-vehicle compatibility
        {"ix_compatibilities_product_vehicle": True},
    )

    def __repr__(self) -> str:
        return f"<Compatibility(id={self.id}, product_id={self.product_id}, vehicle_id={self.vehicle_id})>"
