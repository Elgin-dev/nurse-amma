from typing import Any

from pydantic import BaseModel, Field, field_validator


class PatientDemographics(BaseModel):
    name: str | None = None
    age: str | None = None
    gender: str | None = None

    @field_validator("age", mode="before")
    @classmethod
    def normalize_numeric_age(cls, value: Any) -> Any:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value


class PrescribedMedication(BaseModel):
    drug_name: str
    dosage: str | None = None
    frequency: str | None = None


class LabResult(BaseModel):
    test_name: str
    value: str | None = None
    unit: str | None = None
    reference_range: str | None = None
    abnormality_flag: bool | None = None


class IntelligentDocumentExtraction(BaseModel):
    cleaned_text: str = ""
    patient_demographics: PatientDemographics = Field(
        default_factory=PatientDemographics
    )
    prescribed_medications: list[PrescribedMedication] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    clinical_diagnosis: list[str] = Field(default_factory=list)
    doctor_notes: str | None = None


class IntelligentDocumentResponse(BaseModel):
    filename: str
    extraction_method: str
    raw_ocr_text: str
    structured_data: IntelligentDocumentExtraction
    verification_status: str = "unverified"
    structuring_source: str
