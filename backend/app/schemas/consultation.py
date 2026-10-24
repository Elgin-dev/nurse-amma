from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsultationCreate(BaseModel):
    patient_id: UUID
    language: str = Field(default="en", min_length=2, max_length=10)

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("Language cannot be empty.")
        return value


class ConsultationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    language: str
    status: str
    created_at: datetime
    completed_at: datetime | None