from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TimelineEventType(str, Enum):
    CLINICAL_HISTORY_SUBMITTED = "clinical_history_submitted"
    SUMMARY_GENERATED = "summary_generated"
    RED_FLAG_RECORDED = "red_flag_recorded"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    SUMMARY_REVIEWED = "summary_reviewed"
    RED_FLAG_REVIEWED = "red_flag_reviewed"
    DOCUMENT_VERIFIED = "document_verified"


class TimelineSource(str, Enum):
    PATIENT_REPORTED = "patient_reported"
    GENERATED_SUMMARY = "generated_summary"
    RULE_BASED_RED_FLAG = "rule_based_red_flag"
    DOCUMENT = "document"
    DOCUMENT_EXTRACTED = "document_extracted"
    CLINICIAN_VERIFIED = "clinician_verified"


class TimelineEvent(BaseModel):
    event_id: str
    event_type: TimelineEventType
    occurred_at: datetime
    title: str
    description: Optional[str] = None
    source: TimelineSource
    status: str
    related_entity_id: Optional[UUID] = None
    related_entity_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    consultation_id: UUID
    events: list[TimelineEvent]
    count: int