from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClinicalSummary(Base):
    """A persisted draft generated from a specific history submission."""

    __tablename__ = "clinical_summaries"

    __table_args__ = (
        UniqueConstraint(
            "consultation_id",
            "version",
            name="uq_clinical_summaries_consultation_version",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_clinical_summaries_version_positive",
        ),
        CheckConstraint(
            "review_status IN ('pending_doctor_approval', 'approved', 'rejected', 'needs_correction')",
            name="ck_clinical_summaries_review_status",
        ),
        ForeignKeyConstraint(
            ["consultation_id", "source_submission_id"],
            [
                "clinical_history_submissions.consultation_id",
                "clinical_history_submissions.id",
            ],
            name="fk_clinical_summaries_consultation_submission",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    consultation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(32),
        default="pending_doctor_approval",
        server_default="pending_doctor_approval",
        nullable=False,
    )

    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    corrected_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    corrected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )