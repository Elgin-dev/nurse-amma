from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Consultation, Patient
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationResponse,
)


router = APIRouter(
    prefix="/api/v1/consultations",
    tags=["Consultations"],
)


@router.post(
    "",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_consultation(
    payload: ConsultationCreate,
    db: Session = Depends(get_db),
) -> Consultation:
    patient = db.get(Patient, payload.patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    consultation = Consultation(
        patient_id=patient.id,
        language=payload.language,
    )

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


@router.get(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
def get_consultation(
    consultation_id: UUID,
    db: Session = Depends(get_db),
) -> Consultation:
    consultation = db.scalar(
        select(Consultation).where(
            Consultation.id == consultation_id
        )
    )

    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found.",
        )

    return consultation