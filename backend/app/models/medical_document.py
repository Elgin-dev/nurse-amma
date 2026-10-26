from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MedicalDocument(Base):
    """Persist an uploaded medical file and its OCR/extraction results.

    The original bytes are held in the database so processing can be retried
    after a server restart and does not depend on ephemeral temporary files.
    API responses must never expose ``file_content``.
    """

    __tablename__ = "medical_documents"

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'rejected')",
            name="ck_medical_documents_verification_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    consultation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    processing_status: Mapped[str] = mapped_column(
        String(32), default="processing", server_default="processing", nullable=False
    )
    extraction_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), default="unverified", server_default="unverified", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )