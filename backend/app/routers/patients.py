from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Patient
from app.schemas.patient import PatientCreate, PatientResponse


router = APIRouter(
    prefix="/api/v1/patients",
    tags=["Patients"],
)


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
) -> Patient:
    patient = Patient(
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
    )

    try:
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save patient record.",
        ) from exc


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
)
def get_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> Patient:
    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id)
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    return patient