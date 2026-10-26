from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClinicalHistorySubmission(Base):
    """A versioned structured history snapshot for one consultation."""

    __tablename__ = "clinical_history_submissions"

    __table_args__ = (
        UniqueConstraint(
            "consultation_id",
            "version",
            name="uq_clinical_history_submissions_consultation_version",
        ),
        UniqueConstraint(
            "consultation_id",
            "id",
            name="uq_clinical_history_submissions_consultation_id_id",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_clinical_history_submissions_version_positive",
        ),
        CheckConstraint(
            "schema_version >= 1",
            name="ck_clinical_history_submissions_schema_version_positive",
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

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    schema_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(40),
        default="patient_reported",
        server_default="patient_reported",
        nullable=False,
    )

    verification_status: Mapped[str] = mapped_column(
        String(32),
        default="unverified",
        server_default="unverified",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )