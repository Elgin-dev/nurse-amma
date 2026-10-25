from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access, require_patient_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.consultation import Consultation
from app.models.user import User
from app.schemas.consultation import ConsultationCreate, ConsultationResponse


router = APIRouter(prefix="/api/v1/consultations", tags=["Consultations"])


@router.post("", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
def create_consultation(
    payload: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Consultation:
    # This checks both existence and whether the caller owns the patient record.
    patient = require_patient_access(db, payload.patient_id, current_user)
    consultation = Consultation(patient_id=patient.id, language=payload.language)
    try:
        db.add(consultation)
        db.commit()
        db.refresh(consultation)
        return consultation
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create consultation.",
        ) from exc


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def get_consultation(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Consultation:
    return require_consultation_access(db, consultation_id, current_user)
