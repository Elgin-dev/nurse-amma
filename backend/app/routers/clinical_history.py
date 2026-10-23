import uuid
from fastapi import APIRouter, HTTPException, status
from app.schemas.clinical_history import (
    PatientResponseInput,
    DraftSummaryResponse,
    NextQuestionResponse,
)
from app.services.question_engine import QuestionEngine
from app.services.red_flag_service import RedFlagService
from fastapi import File, UploadFile, Form
from app.services.speech_service import SpeechService

router = APIRouter(prefix="/api/v1/consultations", tags=["Clinical History"])


@router.post("/{consultation_id}/next-question", response_model=NextQuestionResponse)
async def get_next_question(
    consultation_id: str,
    chief_complaint: str,
    answered_keys: list[str] = [],
):
    return QuestionEngine.get_next_question(chief_complaint, answered_keys)


@router.post("/{consultation_id}/summary", response_model=DraftSummaryResponse)
async def generate_draft_summary(
    consultation_id: str,
    payload: PatientResponseInput,
):
    red_flags = RedFlagService.evaluate_red_flags(payload)

    duration_str = (
        f"for {payload.symptom_details.duration.value} {payload.symptom_details.duration.unit.value}"
        if payload.symptom_details.duration
        else ""
    )
    
    hpi = (
        f"Patient reports {payload.chief_complaint} {duration_str}. "
        f"Severity: {payload.symptom_details.severity or 'unspecified'}. "
        f"Progression: {payload.symptom_details.progression or 'unspecified'}. "
        f"Associated symptoms: {', '.join(payload.associated_symptoms) if payload.associated_symptoms else 'None reported'}."
    )

    medication_list = [
        {"name": med, "source_type": "patient_reported", "status": "unverified"}
        for med in payload.current_medications
    ]

    return DraftSummaryResponse(
        summary_id=f"SUM-{uuid.uuid4().hex[:8]}",
        consultation_id=consultation_id,
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
    consultation_id: str,
    language: str = Form("en"),
    file: UploadFile = File(...)
):
    """
    Accepts audio binary input from the patient interface, returns the recognized 
    text transcript, or flags a speech error to switch the UI to touch/text fallback.
    """
    contents = await file.read()
    transcript = await SpeechService.transcribe_audio_chunk(contents, language=language)
    
    if not transcript:
        return {
            "status": "fallback_required",
            "message": "Speech recognition unavailable or low confidence. Please use text input.",
            "transcript": None
        }
        
    return {
        "status": "success",
        "transcript": transcript,
        "language": language
    }