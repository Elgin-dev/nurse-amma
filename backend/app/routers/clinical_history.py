import uuid

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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.clinical_history_submission import ClinicalHistorySubmission
from app.models.clinical_red_flag import ClinicalRedFlag
from app.models.clinical_summary import ClinicalSummary
from app.models.consultation import Consultation
from app.models.user import User
from app.schemas.clinical_history import (
    DraftSummaryResponse,
    NextQuestionResponse,
    PatientResponseInput,
    RedFlagAlert,
)
from app.schemas.clinical_history_persistence import ClinicalHistorySubmissionResponse
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
    """Transcribe audio for an authorized consultation or request text fallback."""
    require_consultation_access(db, consultation_id, current_user)
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
            "message": "Speech recognition is unavailable or failed. Please use text input.",
            "transcript": None,
        }
    return {
        "status": "success",
        "transcript": transcript,
        "language": language,
    }
