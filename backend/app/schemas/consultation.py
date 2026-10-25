from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsultationCreate(BaseModel):
    patient_id: UUID
    language: str = Field(default="en", max_length=10)

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) < 2:
            raise ValueError("Language must contain at least 2 characters.")
        return value


class ConsultationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    language: str
    status: str
    created_at: datetime
    completed_at: datetime | None