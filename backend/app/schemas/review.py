from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SummaryReviewStatus(str, Enum):
    PENDING_DOCTOR_APPROVAL = "pending_doctor_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CORRECTION = "needs_correction"


class RedFlagReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    ACKNOWLEDGED = "acknowledged"
    VERIFIED = "verified"
    DISMISSED = "dismissed"
    CORRECTED = "corrected"


class DocumentVerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class SummaryReviewRequest(BaseModel):
    status: SummaryReviewStatus
    notes: Optional[str] = Field(default=None, max_length=2000)


class SummaryCorrectionRequest(BaseModel):
    """Correction of summary fields. Only supplied fields are changed.

    A correction always resets the summary's review status back to
    ``pending_doctor_approval``; a clinician must re-approve the corrected
    version before it is considered verified.
    """

    chief_complaint: Optional[str] = Field(default=None, max_length=1000)
    history_of_present_illness: Optional[str] = Field(default=None, max_length=10000)
    past_medical_history: Optional[list[str]] = None
    medication_history: Optional[list[dict]] = None
    allergies: Optional[list[str]] = None
    investigation_history: Optional[list[dict]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "SummaryCorrectionRequest":
        if all(
            value is None
            for value in (
                self.chief_complaint,
                self.history_of_present_illness,
                self.past_medical_history,
                self.medication_history,
                self.allergies,
                self.investigation_history,
            )
        ):
            raise ValueError("At least one summary field must be provided for correction.")
        return self


class RedFlagReviewRequest(BaseModel):
    status: RedFlagReviewStatus
    notes: Optional[str] = Field(default=None, max_length=2000)


class DocumentVerifyRequest(BaseModel):
    status: DocumentVerificationStatus
    notes: Optional[str] = Field(default=None, max_length=2000)


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_user_id: Optional[UUID]
    action: str
    entity_type: str
    entity_id: UUID
    consultation_id: UUID
    details: dict[str, Any]
    created_at: datetime