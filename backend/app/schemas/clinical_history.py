from enum import Enum
from typing import List, Optional
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
    consultation_id: str
    chief_complaint: str
    symptom_details: SymptomDetails
    associated_symptoms: List[str] = []
    past_medical_history: List[str] = []
    current_medications: List[str] = []
    allergies: List[str] = []
    source: str = Field(default="patient_reported")


class RedFlagAlert(BaseModel):
    flag_id: str
    severity: str = Field(..., description="high, medium, low")
    trigger: str
    action_required: str


class DraftSummaryResponse(BaseModel):
    summary_id: str
    consultation_id: str
    chief_complaint: str
    history_of_present_illness: str
    past_medical_history: List[str]
    medication_history: List[dict]
    allergies: List[str]
    investigation_history: List[dict] = []
    red_flags: List[RedFlagAlert]
    review_status: str = "pending_doctor_approval"


class NextQuestionResponse(BaseModel):
    question_key: str
    question_text: str
    response_type: str = Field(..., description="text, choice, scale")
    options: Optional[List[str]] = None
    is_complete: bool = False