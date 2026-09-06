"""Knowledge models."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.shop import Shop


class KnowledgeSourceType(str):
    """Knowledge source type enum."""
    PRODUCT = "product"
    FAQ = "faq"
    MANUAL = "manual"
    DELIVERY = "delivery"
    WARRANTY = "warranty"
    POLICY = "policy"
    ARTICLE = "article"
    OTHER = "other"


class KnowledgeDocumentStatus(str):
    """Knowledge document status enum."""
    DRAFT = "draft"
    PROCESSING = "processing"
    ACTIVE = "active"
    INACTIVE = "inactive"


class KnowledgeDocument(Base, UUIDMixin, TimestampMixin):
    """Knowledge document entity."""

    __tablename__ = "knowledge_documents"

    shop_id: Mapped[UUID] = mapped_column(
        ForeignKey("shops.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), default=KnowledgeSourceType.PRODUCT, nullable=False
    )
    source_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=KnowledgeDocumentStatus.DRAFT, nullable=False
    )
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default={}, nullable=True)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="knowledge_documents")
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_knowledge_documents_shop_type_status", "shop_id", "source_type", "status"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, title={self.title}, source_type={self.source_type})>"


class KnowledgeChunk(Base, UUIDMixin, TimestampMixin):
    """Knowledge chunk entity - part of a document for RAG."""

    __tablename__ = "knowledge_chunks"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default={}, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument", back_populates="chunks"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunks_document_index"),
        Index("ix_knowledge_chunks_document", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
