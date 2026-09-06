"""Evaluation run models (doc 9): automated SellerAgent regression tracking."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, UUIDMixin


class EvaluationRun(Base, UUIDMixin, TimestampMixin):
    """A single evaluation pass over an evaluation dataset."""

    __tablename__ = "evaluation_runs"

    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)

    # Relationships
    results: Mapped[List["EvaluationResult"]] = relationship(
        "EvaluationResult", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EvaluationRun(id={self.id}, score={self.score})>"


class EvaluationResult(Base, UUIDMixin, TimestampMixin):
    """Per-case result of an evaluation run."""

    __tablename__ = "evaluation_results"

    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    critical_failure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    actual: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    expected: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    run: Mapped["EvaluationRun"] = relationship(
        "EvaluationRun", back_populates="results"
    )

    def __repr__(self) -> str:
        return f"<EvaluationResult(id={self.id}, case_id={self.case_id}, passed={self.passed})>"
