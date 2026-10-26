from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.audit_event import AuditEvent
from app.models.clinical_history_submission import ClinicalHistorySubmission
from app.models.clinical_red_flag import ClinicalRedFlag
from app.models.clinical_summary import ClinicalSummary
from app.models.medical_document import MedicalDocument
from app.models.user import User
from app.schemas.timeline import (
    TimelineEvent,
    TimelineEventType,
    TimelineResponse,
    TimelineSource,
)


router = APIRouter(
    prefix="/api/v1/consultations",
    tags=["Clinical Timeline"],
)


_AUDIT_EVENT_TYPE_MAP = {
    "summary_review": TimelineEventType.SUMMARY_REVIEWED,
    "summary_correction": TimelineEventType.SUMMARY_REVIEWED,
    "red_flag_review": TimelineEventType.RED_FLAG_REVIEWED,
    "document_verification": TimelineEventType.DOCUMENT_VERIFIED,
}

_AUDIT_TITLE_MAP = {
    "summary_review": "Summary reviewed",
    "summary_correction": "Summary corrected",
    "red_flag_review": "Red flag reviewed",
    "document_verification": "Document verified",
}


@router.get("/{consultation_id}/timeline", response_model=TimelineResponse)
def get_consultation_timeline(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineResponse:
    """Return a permission-checked timeline derived from persisted records.

    Only reflects records already stored in the database for this consultation.
    No events are fabricated; cross-consultation records are excluded by the
    per-entity ``consultation_id`` filters. Clinician actions are surfaced from
    the append-only ``audit_events`` table with source ``clinician_verified``.
    """
    require_consultation_access(db, consultation_id, current_user)

    events: list[TimelineEvent] = []

    submissions = db.scalars(
        select(ClinicalHistorySubmission)
        .where(ClinicalHistorySubmission.consultation_id == consultation_id)
        .order_by(
            ClinicalHistorySubmission.version.asc(),
            ClinicalHistorySubmission.created_at.asc(),
        )
    ).all()
    for submission in submissions:
        events.append(
            TimelineEvent(
                event_id=f"history:{submission.id}",
                event_type=TimelineEventType.CLINICAL_HISTORY_SUBMITTED,
                occurred_at=submission.created_at,
                title=f"Clinical history v{submission.version} submitted",
                description="Patient-reported structured history snapshot.",
                source=TimelineSource.PATIENT_REPORTED,
                status=submission.verification_status,
                related_entity_id=submission.id,
                related_entity_type="clinical_history_submission",
                metadata={
                    "version": submission.version,
                    "schema_version": submission.schema_version,
                },
            )
        )

    summaries = db.scalars(
        select(ClinicalSummary)
        .where(ClinicalSummary.consultation_id == consultation_id)
        .order_by(
            ClinicalSummary.version.asc(),
            ClinicalSummary.created_at.asc(),
        )
    ).all()
    for summary in summaries:
        events.append(
            TimelineEvent(
                event_id=f"summary:{summary.id}",
                event_type=TimelineEventType.SUMMARY_GENERATED,
                occurred_at=summary.created_at,
                title=f"Draft summary v{summary.version} generated",
                description="Generated from a persisted clinical-history submission.",
                source=TimelineSource.GENERATED_SUMMARY,
                status=summary.review_status,
                related_entity_id=summary.id,
                related_entity_type="clinical_summary",
                metadata={
                    "version": summary.version,
                    "source_submission_id": str(summary.source_submission_id),
                },
            )
        )

    red_flags = db.scalars(
        select(ClinicalRedFlag)
        .join(
            ClinicalSummary,
            ClinicalRedFlag.summary_id == ClinicalSummary.id,
        )
        .where(ClinicalSummary.consultation_id == consultation_id)
        .order_by(
            ClinicalRedFlag.created_at.asc(),
            ClinicalRedFlag.id.asc(),
        )
    ).all()
    for flag in red_flags:
        events.append(
            TimelineEvent(
                event_id=f"red_flag:{flag.id}",
                event_type=TimelineEventType.RED_FLAG_RECORDED,
                occurred_at=flag.created_at,
                title=f"Red flag {flag.flag_id} recorded",
                description=flag.trigger,
                source=TimelineSource.RULE_BASED_RED_FLAG,
                status=flag.review_status,
                related_entity_id=flag.id,
                related_entity_type="clinical_red_flag",
                metadata={"severity": flag.severity},
            )
        )

    documents = db.scalars(
        select(MedicalDocument)
        .where(MedicalDocument.consultation_id == consultation_id)
        .order_by(
            MedicalDocument.created_at.asc(),
            MedicalDocument.id.asc(),
        )
    ).all()
    for document in documents:
        events.append(
            TimelineEvent(
                event_id=f"document:{document.id}:uploaded",
                event_type=TimelineEventType.DOCUMENT_UPLOADED,
                occurred_at=document.created_at,
                title=f"Document uploaded: {document.filename}",
                description="Original document stored for this consultation.",
                source=TimelineSource.DOCUMENT,
                status=document.processing_status,
                related_entity_id=document.id,
                related_entity_type="medical_document",
                metadata={
                    "file_size_bytes": document.file_size_bytes,
                    "file_extension": document.file_extension,
                },
            )
        )

        if document.processing_status in {"completed", "failed"}:
            events.append(
                TimelineEvent(
                    event_id=f"document:{document.id}:processed",
                    event_type=TimelineEventType.DOCUMENT_PROCESSED,
                    occurred_at=document.updated_at,
                    title=(
                        "Document extraction completed"
                        if document.processing_status == "completed"
                        else "Document processing failed"
                    ),
                    description=(
                        document.error_message
                        if document.processing_status == "failed"
                        else "Extraction result stored and remains unverified."
                    ),
                    source=TimelineSource.DOCUMENT_EXTRACTED,
                    status=document.verification_status,
                    related_entity_id=document.id,
                    related_entity_type="medical_document",
                    metadata={
                        "extraction_method": document.extraction_method,
                        "page_count": document.page_count,
                    },
                )
            )

    audit_events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.consultation_id == consultation_id)
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    ).all()
    for audit in audit_events:
        event_type = _AUDIT_EVENT_TYPE_MAP.get(audit.action)
        if event_type is None:
            # Unknown audit actions are intentionally not surfaced as
            # clinical events; they would not be user-actionable.
            continue
        details = audit.details or {}
        to_status = str(details.get("to_status", "unknown"))
        events.append(
            TimelineEvent(
                event_id=f"audit:{audit.id}",
                event_type=event_type,
                occurred_at=audit.created_at,
                title=_AUDIT_TITLE_MAP[audit.action],
                description=details.get("notes"),
                source=TimelineSource.CLINICIAN_VERIFIED,
                status=to_status,
                related_entity_id=audit.entity_id,
                related_entity_type=audit.entity_type,
                metadata={
                    "action": audit.action,
                    "from_status": details.get("from_status"),
                    "to_status": to_status,
                },
            )
        )

    events.sort(key=lambda event: (event.occurred_at, event.event_id))
    return TimelineResponse(
        consultation_id=consultation_id,
        events=events,
        count=len(events),
    )