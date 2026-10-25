from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ClinicalHistorySubmissionResponse(BaseModel):
    """Persisted structured clinical-history submission."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consultation_id: UUID
    version: int
    schema_version: int
    payload: dict[str, Any]
    source: str
    verification_status: str
    created_at: datetime