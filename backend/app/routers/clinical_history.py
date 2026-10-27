from io import BytesIO
from pathlib import Path
import uuid
from typing import Any, Dict, List, Literal, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.clinical_history_submission import ClinicalHistorySubmission
from app.models.clinical_red_flag import ClinicalRedFlag
from app.models.clinical_summary import ClinicalSummary
from app.models.consultation import Consultation
from app.models.user import User
from app.schemas.clinical_history import (
    DynamicIntakeRequest,
    DynamicIntakeResponse,
    DraftSummaryResponse,
    ExtractedClinicalContext,
    NextQuestionResponse,
    PatientResponseInput,
    RedFlagAlert,
)
from app.schemas.clinical_history_persistence import ClinicalHistorySubmissionResponse
from app.schemas.intelligent_ocr import IntelligentDocumentResponse
from app.services.conversational_engine import ConversationalEngine
from app.services.intelligent_ocr_service import IntelligentOCRService
from app.services.question_engine import QuestionEngine
from app.services.red_flag_service import RedFlagService
from app.services.speech_service import SpeechService


router = APIRouter(
    prefix="/api/v1/consultations",
    tags=["Clinical History"],
)

HTTP_422_UNPROCESSABLE = getattr(
    status,
    "HTTP_422_UNPROCESSABLE_CONTENT",
    422,
)


def build_summary_response(
    summary: ClinicalSummary,
    alerts: list[ClinicalRedFlag],
) -> DraftSummaryResponse:
    """Build the public response from persisted summary and red-flag records."""
    payload = summary.payload
    red_flags = [
        RedFlagAlert(
            id=str(alert.id),
            flag_id=alert.flag_id,
            severity=alert.severity,
            trigger=alert.trigger,
            action_required=alert.action_required,
            review_status=alert.review_status,
            reviewed_by_user_id=(
                str(alert.reviewed_by_user_id) if alert.reviewed_by_user_id else None
            ),
            reviewed_at=alert.reviewed_at,
            review_notes=alert.review_notes,
        )
        for alert in alerts
    ]
    return DraftSummaryResponse(
        summary_id=f"SUM-{summary.id}",
        consultation_id=str(summary.consultation_id),
        chief_complaint=payload["chief_complaint"],
        history_of_present_illness=payload["history_of_present_illness"],
        past_medical_history=payload["past_medical_history"],
        medication_history=payload["medication_history"],
        allergies=payload["allergies"],
        investigation_history=payload["investigation_history"],
        red_flags=red_flags,
        review_status=summary.review_status,
        reviewed_by_user_id=(
            str(summary.reviewed_by_user_id) if summary.reviewed_by_user_id else None
        ),
        reviewed_at=summary.reviewed_at,
        review_notes=summary.review_notes,
        corrected_by_user_id=(
            str(summary.corrected_by_user_id) if summary.corrected_by_user_id else None
        ),
        corrected_at=summary.corrected_at,
    )


def _clean_history_list(items: list[str]) -> list[str]:
    """Remove placeholder text that users sometimes type into optional fields."""
    invalid_values = {"not provided", "none", "unknown", "n/a", "na", "nil"}
    return [item.strip() for item in items if item.strip().lower() not in invalid_values]


def _parse_duration(duration_str: Optional[str]) -> Optional[dict]:
    """Convert '3 days' into {'value': 3, 'unit': 'days'} for SymptomDetails."""
    if not duration_str:
        return None
    parts = duration_str.strip().lower().split()
    if len(parts) < 2:
        return None
    try:
        value = int(parts[0])
    except ValueError:
        return None
    unit = parts[1].rstrip("s") + "s"
    if unit not in ("hours", "days", "weeks", "months"):
        unit = "days"
    return {"value": value, "unit": unit}


_DYNAMIC_INTAKE_RED_FLAGS = (
    "chest pain",
    "stiff neck",
    "seizure",
    "unconscious",
    "severe shortness of breath",
)

MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_TYPES = {
    ".png": ("image/png", "PNG"),
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
}


@router.post(
    "/{consultation_id}/process-document",
    response_model=IntelligentDocumentResponse,
)
async def process_intake_document(
    consultation_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IntelligentDocumentResponse:
    """OCR and structure an uploaded medical image using local Ollama when available."""
    require_consultation_access(db, consultation_id, current_user)
    try:
        filename = Path((file.filename or "").replace("\\", "/")).name
        if not filename or len(filename) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename must be between 1 and 255 characters.",
            )
        expected = ALLOWED_IMAGE_TYPES.get(Path(filename).suffix.lower())
        if expected is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PNG and JPEG images are supported.",
            )

        content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in {"application/octet-stream", expected[0]}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The declared content type does not match the image extension.",
            )

        image_bytes = await file.read(MAX_IMAGE_SIZE + 1)
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image is empty.",
            )
        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Image size must not exceed 10 MB.",
            )
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                actual_format = image.format
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Image dimensions must not exceed 40 megapixels.",
                    )
                image.verify()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded content is not a valid PNG or JPEG image.",
            ) from exc
        if actual_format != expected[1]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The image content does not match the file extension.",
            )

        result = await run_in_threadpool(
            IntelligentOCRService.process_image,
            image_bytes,
            filename,
        )
        return IntelligentDocumentResponse.model_validate(result)
    finally:
        await file.close()


@router.post(
    "/{consultation_id}/dynamic-intake",
    response_model=DynamicIntakeResponse,
)
async def dynamic_intake(
    consultation_id: uuid.UUID,
    payload: DynamicIntakeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DynamicIntakeResponse:
    """Run one conversational intake turn with a deterministic emergency override."""
    require_consultation_access(db, consultation_id, current_user)
    try:
        payload_consultation_id = uuid.UUID(payload.consultation_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="Invalid consultation_id in request body",
        ) from exc

    if payload_consultation_id != consultation_id:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="consultation_id in request body must match the URL",
        )

    latest_message = payload.chat_history[-1].content
    normalized_message = latest_message.casefold().strip()
    
    # 1. Handle user wanting to end the chat
    if normalized_message in ("end chat", "stop", "quit", "exit", "lets end this chat", "end"):
        # Return a completed state so the UI shows the finish button
        return DynamicIntakeResponse(
            status="COMPLETED",
            next_question="",
            extracted_data=ExtractedClinicalContext(
                chief_complaint="Session ended by user",
                is_complete=True
            )
        )

    # 2. Handle Red Flag Emergencies
    matched_red_flag = next(
        (
            trigger
            for trigger in _DYNAMIC_INTAKE_RED_FLAGS
            if trigger in normalized_message
        ),
        None,
    )
    if matched_red_flag:
        # 1. Save the emergency to the DB so the dashboard can find it
        emergency_payload = {
            "consultation_id": str(consultation_id),
            "chief_complaint": latest_message,
            "symptom_details": {
                "severity": "severe",
                "progression": "unspecified",
                "location": None,
                "duration": None,
            },
            "associated_symptoms": ["Emergency Red Flag Triggered"],
            "past_medical_history": [],
            "current_medications": [],
            "allergies": [],
            "question_key": "red_flag",
            "question_text": "Emergency Triage",
            "answer_text": f"Patient reported: {matched_red_flag}",
            "source": "patient_reported",
        }
        
        try:
            validated_payload = PatientResponseInput.model_validate(emergency_payload)
            latest_submission = db.scalar(
                select(ClinicalHistorySubmission)
                .where(ClinicalHistorySubmission.consultation_id == consultation_id)
                .order_by(ClinicalHistorySubmission.version.desc())
                .limit(1)
            )
            serialized = validated_payload.model_dump(mode="json")
            if latest_submission is None or latest_submission.payload != serialized:
                next_version = (latest_submission.version if latest_submission else 0) + 1
                submission = ClinicalHistorySubmission(
                    consultation_id=consultation_id,
                    version=next_version,
                    schema_version=1,
                    payload=serialized,
                    source="patient_reported",
                    verification_status="unverified",
                )
                db.add(submission)
                db.commit()
        except Exception:
            db.rollback()

        # 2. Return the emergency response to lock the chat
        return DynamicIntakeResponse(
            status="EMERGENCY_ESCALATION",
            next_question=(
                "Please seek emergency medical care now or contact your local "
                "emergency number. Do not wait for this chat to continue."
            ),
            extracted_data=ExtractedClinicalContext(
                chief_complaint=latest_message,
                severity="severe",
                associated_symptoms=["Emergency Red Flag Triggered"],
                is_complete=True,
            ),
            red_flag_alert={
                "flag_id": "RF-DYNAMIC-001",
                "severity": "high",
                "trigger": f"Patient reported: {matched_red_flag}",
                "action_required": (
                    "Immediate emergency medical assessment is advised. "
                    "This chat is not an emergency service."
                ),
            },
        )

    chat_history = [
        message.model_dump()
        for message in payload.chat_history
    ]
    
    # PASS THE LANGUAGE TO THE ENGINE
    engine_result = await run_in_threadpool(
        ConversationalEngine.process_turn_local,
        chat_history,
        payload.language,  # <-- THIS IS THE NEW LINE
    )
    
    extracted_data = ExtractedClinicalContext.model_validate(
        engine_result["extracted_data"]
    )
    complete = extracted_data.is_complete and ConversationalEngine._has_review_details(
        extracted_data
    )
    extracted_data.is_complete = complete
    # Filter out the chief complaint from associated symptoms (prevents "headache: headache" bugs)
    chief_lower = (extracted_data.chief_complaint or "").strip().lower()
    cleaned = []
    for s in (extracted_data.associated_symptoms or []):
        s_strip = s.strip()
        if not s_strip:
            continue
        if s_strip.lower() == chief_lower:
            continue
        if s_strip.lower() in {"none", "n/a", "null"}:
            continue
        cleaned.append(s_strip)
    extracted_data.associated_symptoms = cleaned if cleaned else ["None reported"]

    doctor_summary = None
    next_question = engine_result.get("next_question", "")
    if complete:
        next_question = ""
        doctor_summary = {
            "consultation_id": str(consultation_id),
            "chief_complaint": extracted_data.chief_complaint,
            "duration": extracted_data.duration,
            "severity": extracted_data.severity,
            "fever_mechanism": extracted_data.fever_mechanism,
            "associated_symptoms": extracted_data.associated_symptoms,
            "aggravating_relieving_factors": (
                extracted_data.aggravating_relieving_factors
            ),
            "clinical_review_note": (
                "Patient-reported history for clinician review; not a diagnosis."
            ),
        }
    elif not next_question:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Clinical intake engine did not return a follow-up question",
        )

    # --- SAVE THE COMPLETED CHAT TO THE DATABASE ---
    if complete:
        duration_parsed = _parse_duration(extracted_data.duration)

        extra_notes = []
        if extracted_data.fever_mechanism:
            extra_notes.append(f"Symptom characteristics: {extracted_data.fever_mechanism}.")
        if extracted_data.aggravating_relieving_factors:
            extra_notes.append(
                f"Aggravating/relieving factors: {extracted_data.aggravating_relieving_factors}."
            )

        intake_payload = {
            "consultation_id": str(consultation_id),
            "chief_complaint": extracted_data.chief_complaint or "Not provided",
            "symptom_details": {
                "duration": duration_parsed,
                "severity": extracted_data.severity,
                "progression": extracted_data.fever_mechanism,
                "location": None,
            },
            "associated_symptoms": list(extracted_data.associated_symptoms or []),
            "past_medical_history": [],
            "current_medications": [],
            "allergies": [],
            "question_key": None,
            "question_text": "AI conversational intake",
            "answer_text": " ".join(extra_notes) if extra_notes else None,
            "source": "patient_reported",
        }

        try:
            validated_payload = PatientResponseInput.model_validate(intake_payload)
        except Exception:
            validated_payload = None

        if validated_payload is not None:
            latest_submission = db.scalar(
                select(ClinicalHistorySubmission)
                .where(ClinicalHistorySubmission.consultation_id == consultation_id)
                .order_by(ClinicalHistorySubmission.version.desc())
                .limit(1)
            )
            serialized = validated_payload.model_dump(mode="json")
            if latest_submission is None or latest_submission.payload != serialized:
                next_version = (latest_submission.version if latest_submission else 0) + 1
                try:
                    submission = ClinicalHistorySubmission(
                        consultation_id=consultation_id,
                        version=next_version,
                        schema_version=1,
                        payload=serialized,
                        source="patient_reported",
                        verification_status="unverified",
                    )
                    db.add(submission)
                    db.commit()
                except Exception:
                    db.rollback()

    return DynamicIntakeResponse(
        status="COMPLETED" if complete else "IN_PROGRESS",
        next_question=next_question,
        extracted_data=extracted_data,
        doctor_summary=doctor_summary,
    )


@router.post(
    "/{consultation_id}/responses",
    response_model=ClinicalHistorySubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_clinical_history_response(
    consultation_id: uuid.UUID,
    payload: PatientResponseInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a versioned, explicitly patient-reported history snapshot."""
    try:
        payload_consultation_id = uuid.UUID(payload.consultation_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="Invalid consultation_id in request body",
        ) from exc

    if payload_consultation_id != consultation_id:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="consultation_id in request body must match the URL",
        )

    require_consultation_access(db, consultation_id, current_user)
    consultation = db.scalar(
        select(Consultation)
        .where(Consultation.id == consultation_id)
        .with_for_update()
    )
    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found",
        )

    current_version = db.scalar(
        select(func.max(ClinicalHistorySubmission.version)).where(
            ClinicalHistorySubmission.consultation_id == consultation_id
        )
    )

    payload_data = payload.model_dump(mode="json")
    # Server-side assignment is intentional: this endpoint records patient input.
    payload_data["source"] = "patient_reported"
    # Normalize optional lists to prevent literal "Not provided" from becoming a clinical fact.
    payload_data["associated_symptoms"] = _clean_history_list(payload.associated_symptoms)
    payload_data["past_medical_history"] = _clean_history_list(payload.past_medical_history)
    payload_data["current_medications"] = _clean_history_list(payload.current_medications)
    payload_data["allergies"] = _clean_history_list(payload.allergies)
    submission = ClinicalHistorySubmission(
        consultation_id=consultation_id,
        version=(current_version or 0) + 1,
        schema_version=1,
        payload=payload_data,
        source="patient_reported",
        verification_status="unverified",
    )

    try:
        db.add(submission)
        db.commit()
        db.refresh(submission)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create the next history version; retry the request",
        ) from exc
    except Exception:
        db.rollback()
        raise

    return submission


@router.post(
    "/{consultation_id}/next-question",
    response_model=NextQuestionResponse,
)
def get_next_question(
    consultation_id: uuid.UUID,
    chief_complaint: str,
    answered_keys: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate the next question for an authorized consultation."""
    require_consultation_access(db, consultation_id, current_user)
    return QuestionEngine.get_next_question(chief_complaint, answered_keys or [])


@router.post(
    "/{consultation_id}/summary",
    response_model=DraftSummaryResponse,
)
def generate_draft_summary(
    consultation_id: uuid.UUID,
    payload: PatientResponseInput | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and persist a draft summary and its red-flag findings.

    A caller-supplied payload is treated as patient-reported input only. If no
    payload is supplied, the latest persisted submission is used.
    """
    require_consultation_access(db, consultation_id, current_user)
    consultation = db.scalar(
        select(Consultation)
        .where(Consultation.id == consultation_id)
        .with_for_update()
    )
    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found",
        )

    latest_submission = db.scalar(
        select(ClinicalHistorySubmission)
        .where(ClinicalHistorySubmission.consultation_id == consultation_id)
        .order_by(ClinicalHistorySubmission.version.desc())
        .limit(1)
    )

    new_submission = False
    if payload is not None:
        try:
            payload_consultation_id = uuid.UUID(payload.consultation_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="Invalid consultation_id in request body",
            ) from exc

        if payload_consultation_id != consultation_id:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="consultation_id in request body must match the URL",
            )

        payload_data = payload.model_dump(mode="json")
        payload_data["source"] = "patient_reported"
        # Normalize optional lists to prevent literal "Not provided" from becoming a clinical fact.
        payload_data["associated_symptoms"] = _clean_history_list(payload.associated_symptoms)
        payload_data["past_medical_history"] = _clean_history_list(payload.past_medical_history)
        payload_data["current_medications"] = _clean_history_list(payload.current_medications)
        payload_data["allergies"] = _clean_history_list(payload.allergies)
        if latest_submission is not None and latest_submission.payload == payload_data:
            submission = latest_submission
        else:
            current_submission_version = latest_submission.version if latest_submission else 0
            submission = ClinicalHistorySubmission(
                consultation_id=consultation_id,
                version=current_submission_version + 1,
                schema_version=1,
                payload=payload_data,
                source="patient_reported",
                verification_status="unverified",
            )
            new_submission = True
    else:
        if latest_submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No saved clinical history submission found",
            )
        submission = latest_submission
        payload = PatientResponseInput.model_validate(submission.payload)

    assert payload is not None
    red_flags = RedFlagService.evaluate_red_flags(payload)

    duration_str = (
        f"for {payload.symptom_details.duration.value} "
        f"{payload.symptom_details.duration.unit.value}"
        if payload.symptom_details.duration
        else ""
    )
    associated_symptoms_text = ", ".join(payload.associated_symptoms) if payload.associated_symptoms else "Not provided"
    hpi = (
        f"Patient reports {payload.chief_complaint} {duration_str}. "
        f"Severity: {payload.symptom_details.severity or 'unspecified'}. "
        f"Progression: {payload.symptom_details.progression or 'unspecified'}. "
        f"Associated symptoms: {associated_symptoms_text}."
    )
    if payload.answer_text:
        question_label = payload.question_text or "the clinical follow-up question"
        hpi += f" Patient's answer to '{question_label}': {payload.answer_text}."
    medication_list = [
        {
            "name": medication,
            "source_type": "patient_reported",
            "status": "unverified",
        }
        for medication in payload.current_medications
    ]

    next_summary_version = (
        db.scalar(
            select(func.max(ClinicalSummary.version)).where(
                ClinicalSummary.consultation_id == consultation_id
            )
        )
        or 0
    ) + 1
    summary_payload = {
        "chief_complaint": payload.chief_complaint,
        "history_of_present_illness": hpi,
        "past_medical_history": payload.past_medical_history,
        "medication_history": medication_list,
        "allergies": payload.allergies,
        "investigation_history": [],
    }

    try:
        if new_submission:
            db.add(submission)
            db.flush()

        summary = ClinicalSummary(
            consultation_id=consultation_id,
            source_submission_id=submission.id,
            version=next_summary_version,
            payload=summary_payload,
            review_status="pending_doctor_approval",
        )
        db.add(summary)
        db.flush()

        alert_records = [
            ClinicalRedFlag(
                summary_id=summary.id,
                flag_id=alert.flag_id,
                severity=alert.severity,
                trigger=alert.trigger,
                action_required=alert.action_required,
                review_status="pending_review",
            )
            for alert in red_flags
        ]
        db.add_all(alert_records)
        db.commit()
        db.refresh(summary)

        saved_alerts = db.scalars(
            select(ClinicalRedFlag)
            .where(ClinicalRedFlag.summary_id == summary.id)
            .order_by(ClinicalRedFlag.created_at, ClinicalRedFlag.id)
        ).all()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not persist the clinical summary; retry the request",
        ) from exc
    except Exception:
        db.rollback()
        raise

    return build_summary_response(summary, saved_alerts)


@router.get(
    "/{consultation_id}/summary",
    response_model=DraftSummaryResponse,
)
def get_saved_summary(
    consultation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the latest persisted summary and red-flag findings."""
    require_consultation_access(db, consultation_id, current_user)
    summary = db.scalar(
        select(ClinicalSummary)
        .where(ClinicalSummary.consultation_id == consultation_id)
        .order_by(ClinicalSummary.version.desc())
        .limit(1)
    )
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved clinical summary found",
        )

    alerts = db.scalars(
        select(ClinicalRedFlag)
        .where(ClinicalRedFlag.summary_id == summary.id)
        .order_by(ClinicalRedFlag.created_at, ClinicalRedFlag.id)
    ).all()
    return build_summary_response(summary, alerts)


@router.post("/{consultation_id}/process-speech")
async def process_patient_speech(
    consultation_id: uuid.UUID,
    language: str = Form("en"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_consultation_access(db, consultation_id, current_user)
    
    MAX_AUDIO_SIZE = 5 * 1024 * 1024
    transcript = None
    try:
        # Read inside try so file.close() is guaranteed to run
        contents = await file.read(MAX_AUDIO_SIZE + 1)
        if len(contents) > MAX_AUDIO_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Audio file must not exceed 5 MB.",
            )
            
        transcript = await SpeechService.transcribe_audio_chunk(contents, language=language)
    finally:
        await file.close()

    if not transcript:
        return {"status": "fallback_required", "message": "Speech recognition is unavailable or failed. Please use text input.", "transcript": None}
    return {"status": "success", "transcript": transcript, "language": language}