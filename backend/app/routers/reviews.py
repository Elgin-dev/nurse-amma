from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.audit_event import AuditEvent
from app.models.clinical_red_flag import ClinicalRedFlag
from app.models.clinical_summary import ClinicalSummary
from app.models.medical_document import MedicalDocument
from app.models.user import User
from app.routers.clinical_history import build_summary_response
from app.schemas.clinical_history import DraftSummaryResponse, RedFlagAlert
from app.schemas.review import (
    DocumentVerifyRequest,
    RedFlagReviewRequest,
    SummaryCorrectionRequest,
    SummaryReviewRequest,
)


router = APIRouter(prefix="/api/v1", tags=["Clinical Review"])


SUMMARY_REVIEW_TRANSITIONS: dict[str, set[str]] = {
    "pending_doctor_approval": {"approved", "rejected", "needs_correction"},
    "needs_correction": {"approved", "rejected"},
}

RED_FLAG_REVIEW_TRANSITIONS: dict[str, set[str]] = {
    "pending_review": {"acknowledged", "verified", "dismissed", "corrected"},
    "acknowledged": {"verified", "dismissed", "corrected"},
}

DOCUMENT_VERIFICATION_TRANSITIONS: dict[str, set[str]] = {
    "unverified": {"verified", "rejected"},
}


def _load_summary(db: Session, summary_id: UUID) -> ClinicalSummary:
    summary = db.get(ClinicalSummary, summary_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinical summary not found",
        )
    return summary


def _load_red_flag(db: Session, flag_id: UUID) -> ClinicalRedFlag:
    flag = db.get(ClinicalRedFlag, flag_id)
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Red flag not found",
        )
    return flag


def _load_document(db: Session, document_id: UUID) -> MedicalDocument:
    document = db.get(MedicalDocument, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical document not found",
        )
    return document


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    consultation_id: UUID,
    details: dict,
) -> None:
    """Add (do not commit) one immutable audit-event record."""
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            consultation_id=consultation_id,
            details=details,
        )
    )


def _summary_alerts(db: Session, summary_id: UUID) -> list[ClinicalRedFlag]:
    return list(
        db.scalars(
            select(ClinicalRedFlag)
            .where(ClinicalRedFlag.summary_id == summary_id)
            .order_by(ClinicalRedFlag.created_at, ClinicalRedFlag.id)
        ).all()
    )


@router.post(
    "/summaries/{summary_id}/review",
    response_model=DraftSummaryResponse,
)
def review_summary(
    summary_id: UUID,
    payload: SummaryReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftSummaryResponse:
    """Record an authorized clinician's review of a persisted draft summary."""
    summary = _load_summary(db, summary_id)
    require_consultation_access(db, summary.consultation_id, current_user)

    requested = payload.status.value
    if requested not in SUMMARY_REVIEW_TRANSITIONS.get(summary.review_status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition summary from {summary.review_status} "
                f"to {requested}."
            ),
        )

    previous = summary.review_status
    summary.review_status = requested
    summary.reviewed_by_user_id = current_user.id
    summary.reviewed_at = datetime.now(timezone.utc)
    summary.review_notes = payload.notes

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="summary_review",
        entity_type="clinical_summary",
        entity_id=summary.id,
        consultation_id=summary.consultation_id,
        details={
            "from_status": previous,
            "to_status": requested,
            "notes": payload.notes,
        },
    )

    try:
        db.commit()
        db.refresh(summary)
    except Exception:
        db.rollback()
        raise

    return build_summary_response(summary, _summary_alerts(db, summary.id))


@router.patch(
    "/summaries/{summary_id}",
    response_model=DraftSummaryResponse,
)
def correct_summary(
    summary_id: UUID,
    payload: SummaryCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftSummaryResponse:
    """Correct summary fields; the review status is reset to pending.

    A correction is an explicit clinician action that invalidates any previous
    review. The summary must be re-reviewed before it is considered verified.
    Both the before/after payloads and the status change are recorded in the
    audit trail.
    """
    summary = _load_summary(db, summary_id)
    require_consultation_access(db, summary.consultation_id, current_user)

    before_payload = dict(summary.payload)
    after_payload = dict(before_payload)
    for field in (
        "chief_complaint",
        "history_of_present_illness",
        "past_medical_history",
        "medication_history",
        "allergies",
        "investigation_history",
    ):
        value = getattr(payload, field)
        if value is not None:
            after_payload[field] = value

    previous_status = summary.review_status
    summary.payload = after_payload
    summary.review_status = "pending_doctor_approval"
    summary.corrected_by_user_id = current_user.id
    summary.corrected_at = datetime.now(timezone.utc)
    # The previous review is no longer valid; clear the reviewer fields.
    summary.reviewed_by_user_id = None
    summary.reviewed_at = None
    summary.review_notes = None

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="summary_correction",
        entity_type="clinical_summary",
        entity_id=summary.id,
        consultation_id=summary.consultation_id,
        details={
            "from_status": previous_status,
            "to_status": "pending_doctor_approval",
            "notes": payload.notes,
            "before": before_payload,
            "after": after_payload,
        },
    )

    try:
        db.commit()
        db.refresh(summary)
    except Exception:
        db.rollback()
        raise

    return build_summary_response(summary, _summary_alerts(db, summary.id))


@router.post(
    "/red-flags/{flag_id}/review",
    response_model=RedFlagAlert,
)
def review_red_flag(
    flag_id: UUID,
    payload: RedFlagReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedFlagAlert:
    """Record an authorized clinician's review of a persisted red-flag finding."""
    flag = _load_red_flag(db, flag_id)
    summary = db.get(ClinicalSummary, flag.summary_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated clinical summary not found",
        )
    require_consultation_access(db, summary.consultation_id, current_user)

    requested = payload.status.value
    if requested not in RED_FLAG_REVIEW_TRANSITIONS.get(flag.review_status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition red flag from {flag.review_status} "
                f"to {requested}."
            ),
        )

    previous = flag.review_status
    flag.review_status = requested
    flag.reviewed_by_user_id = current_user.id
    flag.reviewed_at = datetime.now(timezone.utc)
    flag.review_notes = payload.notes

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="red_flag_review",
        entity_type="clinical_red_flag",
        entity_id=flag.id,
        consultation_id=summary.consultation_id,
        details={
            "from_status": previous,
            "to_status": requested,
            "notes": payload.notes,
            "flag_id": flag.flag_id,
        },
    )

    try:
        db.commit()
        db.refresh(flag)
    except Exception:
        db.rollback()
        raise

    return RedFlagAlert(
        id=str(flag.id),
        flag_id=flag.flag_id,
        severity=flag.severity,
        trigger=flag.trigger,
        action_required=flag.action_required,
        review_status=flag.review_status,
        reviewed_by_user_id=(
            str(flag.reviewed_by_user_id) if flag.reviewed_by_user_id else None
        ),
        reviewed_at=flag.reviewed_at,
        review_notes=flag.review_notes,
    )


@router.post("/documents/{document_id}/verify")
def verify_document(
    document_id: UUID,
    payload: DocumentVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Record an authorized clinician's verification or rejection of a document."""
    document = _load_document(db, document_id)
    require_consultation_access(db, document.consultation_id, current_user)

    requested = payload.status.value
    if requested not in DOCUMENT_VERIFICATION_TRANSITIONS.get(
        document.verification_status, set()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition document from {document.verification_status} "
                f"to {requested}."
            ),
        )

    previous = document.verification_status
    document.verification_status = requested
    document.verified_by_user_id = current_user.id
    document.verified_at = datetime.now(timezone.utc)
    document.verification_notes = payload.notes

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="document_verification",
        entity_type="medical_document",
        entity_id=document.id,
        consultation_id=document.consultation_id,
        details={
            "from_status": previous,
            "to_status": requested,
            "notes": payload.notes,
            "filename": document.filename,
        },
    )

    try:
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        raise

    return {
        "id": str(document.id),
        "consultation_id": str(document.consultation_id),
        "verification_status": document.verification_status,
        "verified_by_user_id": (
            str(document.verified_by_user_id)
            if document.verified_by_user_id
            else None
        ),
        "verified_at": (
            document.verified_at.isoformat() if document.verified_at else None
        ),
        "verification_notes": document.verification_notes,
    }