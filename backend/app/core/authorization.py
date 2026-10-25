from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.patient import Patient
from app.models.user import User


def require_patient_access(db: Session, patient_id: UUID, user: User) -> Patient:
    """Enforce patient ownership; administrators can manage all records."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if user.role != "admin" and patient.created_by_user_id != user.id:
        # Return 404 rather than revealing that another clinician's record exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def require_consultation_access(db: Session, consultation_id: UUID, user: User) -> Consultation:
    """Enforce access to consultations owned by the caller or administrator."""
    consultation = db.get(Consultation, consultation_id)
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    if user.role == "admin":
        return consultation
    patient = db.get(Patient, consultation.patient_id)
    if patient is None or patient.created_by_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return consultation
