
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.consultation import Consultation
from app.schemas.clinical_history import (
    PatientResponseInput,
    DraftSummaryResponse,
    NextQuestionResponse,
)
from app.services.question_engine import QuestionEngine
from app.services.red_flag_service import RedFlagService
from app.services.speech_service import SpeechService


router = APIRouter(
    prefix="/api/v1/consultations",
    tags=["Clinical History"],
)


def require_consultation(
    db: Session,
    consultation_id: uuid.UUID,
) -> Consultation:
    """Return an existing consultation or raise HTTP 404."""
    consultation = db.get(Consultation, consultation_id)

    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found",
        )

    return consultation


@router.post(
    "/{consultation_id}/next-question",
    response_model=NextQuestionResponse,
)
def get_next_question(
    consultation_id: uuid.UUID,
    chief_complaint: str,
    answered_keys: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Generate the next question for an existing consultation."""
    require_consultation(db, consultation_id)

    return QuestionEngine.get_next_question(
        chief_complaint,
        answered_keys or [],
    )


@router.post(
    "/{consultation_id}/summary",
    response_model=DraftSummaryResponse,
)
def generate_draft_summary(
    consultation_id: uuid.UUID,
    payload: PatientResponseInput,
    db: Session = Depends(get_db),
):
    """Generate a draft summary for an existing consultation."""

    try:
        payload_consultation_id = uuid.UUID(payload.consultation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid consultation_id in request body",
        )

    if payload_consultation_id != consultation_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="consultation_id in request body must match the URL",
        )

    require_consultation(db, consultation_id)

    red_flags = RedFlagService.evaluate_red_flags(payload)

    duration_str = (
        f"for {payload.symptom_details.duration.value} "
        f"{payload.symptom_details.duration.unit.value}"
        if payload.symptom_details.duration
        else ""
    )

    hpi = (
        f"Patient reports {payload.chief_complaint} {duration_str}. "
        f"Severity: {payload.symptom_details.severity or 'unspecified'}. "
        f"Progression: {payload.symptom_details.progression or 'unspecified'}. "
        f"Associated symptoms: "
        f"{', '.join(payload.associated_symptoms) if payload.associated_symptoms else 'None reported'}."
    )

    medication_list = [
        {
            "name": medication,
            "source_type": "patient_reported",
            "status": "unverified",
        }
        for medication in payload.current_medications
    ]

    return DraftSummaryResponse(
        summary_id=f"SUM-{uuid.uuid4().hex[:8]}",
        consultation_id=str(consultation_id),
        chief_complaint=payload.chief_complaint,
        history_of_present_illness=hpi,
        past_medical_history=payload.past_medical_history,
        medication_history=medication_list,
        allergies=payload.allergies,
        investigation_history=[],
        red_flags=red_flags,
        review_status="pending_doctor_approval",
    )


@router.post("/{consultation_id}/process-speech")
async def process_patient_speech(
    consultation_id: uuid.UUID,
    language: str = Form("en"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Transcribe audio for an existing consultation or request text fallback."""
    require_consultation(db, consultation_id)

    contents = await file.read()

    try:
        transcript = await SpeechService.transcribe_audio_chunk(
            contents,
            language=language,
        )
    finally:
        await file.close()

    if not transcript:
        return {
            "status": "fallback_required",
            "message": (
                "Speech recognition is unavailable or failed. "
                "Please use text input."
            ),
            "transcript": None,
        }

    return {
        "status": "success",
        "transcript": transcript,
        "language": language,
    }
