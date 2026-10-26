from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsentCreate(BaseModel):
    consent_version: str = Field(default="1.0", max_length=32)


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    patient_id: UUID
    consent_version: str
    consented_at: datetime