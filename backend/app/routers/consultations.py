from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access, require_patient_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.consultation import Consultation
from app.models.patient import Patient
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


# --- SEARCH ROUTE MUST COME BEFORE /{consultation_id} ---
@router.get("/search")
def search_consultations(
    patient_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find recent consultations by patient name for the doctor dashboard."""
    query = (
        select(Consultation)
        .join(Patient, Consultation.patient_id == Patient.id)
        .where(func.lower(Patient.full_name).contains(patient_name.lower()))
        .order_by(Consultation.created_at.desc())
        .limit(10)
    )
    if current_user.role != "admin":
        query = query.where(Patient.created_by_user_id == current_user.id)
    
    consultations = db.scalars(query).all()
    results = []
    for c in consultations:
        patient = db.get(Patient, c.patient_id)
        results.append({
            "id": str(c.id),
            "patient_name": patient.full_name if patient else "Unknown",
            "created_at": c.created_at.isoformat(),
        })
    return results
# --------------------------------------------------------


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def get_consultation(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Consultation:
    return require_consultation_access(db, consultation_id, current_user)