from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    REPORTED = "reported"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class DurationUnit(str, Enum):
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class Duration(BaseModel):
    value: int = Field(..., gt=0, description="Duration numeric value")
    unit: DurationUnit


class SymptomDetails(BaseModel):
    duration: Optional[Duration] = None
    severity: Optional[str] = Field(None, description="e.g., mild, moderate, severe")
    progression: Optional[str] = Field(None, description="e.g., worsening, improving, constant")
    location: Optional[str] = None


class PatientResponseInput(BaseModel):
    """Patient-reported consultation history, including the raw follow-up answer."""

    consultation_id: str
    chief_complaint: str
    symptom_details: SymptomDetails
    associated_symptoms: List[str] = Field(default_factory=list)
    past_medical_history: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    # Optional Q&A fields preserve backward compatibility with earlier clients.
    question_key: Optional[str] = Field(default=None, max_length=100)
    question_text: Optional[str] = Field(default=None, max_length=500)
    answer_text: Optional[str] = Field(default=None, max_length=5000)
    source: Literal["patient_reported"] = "patient_reported"


class RedFlagReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    ACKNOWLEDGED = "acknowledged"
    VERIFIED = "verified"
    DISMISSED = "dismissed"
    CORRECTED = "corrected"


class RedFlagAlert(BaseModel):
    # ``id`` is the persisted database UUID required for review actions.
    # ``flag_id`` remains the rule identifier (e.g. RF-001) and is kept for
    # backward compatibility and display.
    id: Optional[str] = None
    flag_id: str
    severity: str = Field(..., description="high, medium, low")
    trigger: str
    action_required: str
    review_status: RedFlagReviewStatus = RedFlagReviewStatus.PENDING_REVIEW
    reviewed_by_user_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None


class DraftSummaryResponse(BaseModel):
    summary_id: str
    consultation_id: str
    chief_complaint: str
    history_of_present_illness: str
    past_medical_history: List[str]
    medication_history: List[dict]
    allergies: List[str]
    investigation_history: List[dict] = Field(default_factory=list)
    red_flags: List[RedFlagAlert]
    review_status: str = "pending_doctor_approval"
    reviewed_by_user_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    corrected_by_user_id: Optional[str] = None
    corrected_at: Optional[datetime] = None


class NextQuestionResponse(BaseModel):
    question_key: str
    question_text: str
    response_type: str = Field(..., description="text, choice, scale")
    options: Optional[List[str]] = None
    is_complete: bool = False