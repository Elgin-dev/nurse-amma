from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClinicalRedFlag(Base):
    """A red-flag finding associated with a persisted clinical summary."""

    __tablename__ = "clinical_red_flags"

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending_review', 'acknowledged', 'verified', 'dismissed', 'corrected')",
            name="ck_clinical_red_flags_review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    summary_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clinical_summaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    flag_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    trigger: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    action_required: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(24),
        default="pending_review",
        server_default="pending_review",
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )