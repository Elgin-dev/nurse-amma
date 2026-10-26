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
from app.models.patient_consent import PatientConsent
from app.schemas.consent import ConsentCreate, ConsentResponse

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
        db.flush() # Get the patient ID without committing
        
        # Atomically create the consent record
        consent = PatientConsent(
            patient_id=patient.id,
            consented_by_user_id=current_user.id,
            consent_version="1.0"
        )
        db.add(consent)
        
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
@router.post("/{patient_id}/consent", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
def record_patient_consent(
    patient_id: UUID,
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientConsent:
    """Record explicit consent for data processing for a specific patient."""
    # This verifies the patient exists AND that the current user owns the record
    require_patient_access(db, patient_id, current_user)
    
    consent = PatientConsent(
        patient_id=patient_id,
        consented_by_user_id=current_user.id,
        consent_version=payload.consent_version,
    )
    try:
        db.add(consent)
        db.commit()
        db.refresh(consent)
        return consent
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to record patient consent.",
        ) from exc