from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.authorization import require_patient_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientResponse


router = APIRouter(prefix="/api/v1/patients", tags=["Patients"])


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Patient:
    patient = Patient(
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
        created_by_user_id=current_user.id,
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


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Patient:
    return require_patient_access(db, patient_id, current_user)
