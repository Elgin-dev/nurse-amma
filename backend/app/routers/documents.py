from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.medical_document import MedicalDocument
from app.models.user import User
from app.services.document_service import process_medical_document
from app.services.entity_extraction import extract_laboratory_entities
from app.services.ocr_service import extract_image_text


router = APIRouter(tags=["Medical Documents"])
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def _extract_bytes(content: bytes, suffix: str, original_filename: str) -> dict[str, Any]:
    """Reuse the existing PDF/OCR services while isolating temporary files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / f"upload{suffix}"
        file_path.write_bytes(content)

        if suffix == ".pdf":
            result = process_medical_document(str(file_path))
            extraction_method = "PDF text extraction"
        else:
            result = extract_image_text(str(file_path))
            result["entities"] = extract_laboratory_entities(
                text=result.get("text", ""), page_number=1
            )
            extraction_method = "Tesseract OCR"

    return {
        "filename": original_filename,
        "text": result.get("text", ""),
        "entities": result.get("entities", []),
        "page_count": result.get("page_count", 1),
        "extraction_method": extraction_method,
        "verification_status": result.get("verification_status", "unverified"),
    }


def _document_response(document: MedicalDocument) -> dict[str, Any]:
    """API-safe representation; never include the original binary bytes."""
    return {
        "id": str(document.id),
        "consultation_id": str(document.consultation_id),
        "uploaded_by_user_id": (
            str(document.uploaded_by_user_id) if document.uploaded_by_user_id else None
        ),
        "filename": document.filename,
        "file_extension": document.file_extension,
        "mime_type": document.mime_type,
        "file_size_bytes": document.file_size_bytes,
        "processing_status": document.processing_status,
        "extraction_method": document.extraction_method,
        "page_count": document.page_count,
        "text": document.extracted_text,
        "entities": document.entities or [],
        "verification_status": document.verification_status,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _save_failed_state(db: Session, document: MedicalDocument, message: str) -> None:
    document.processing_status = "failed"
    document.error_message = message[:2000]
    db.add(document)
    db.commit()
    db.refresh(document)


def _persist_extraction(db: Session, document: MedicalDocument, result: dict[str, Any]) -> dict[str, Any]:
    document.extracted_text = result["text"]
    document.entities = result["entities"]
    document.page_count = result["page_count"]
    document.extraction_method = result["extraction_method"]
    document.verification_status = result["verification_status"]
    document.processing_status = "completed"
    document.error_message = None
    db.add(document)
    db.commit()
    db.refresh(document)
    return _document_response(document)


def _reprocess_document(db: Session, document: MedicalDocument) -> dict[str, Any]:
    document.processing_status = "processing"
    document.error_message = None
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        result = _extract_bytes(document.file_content, document.file_extension, document.filename)
    except (ValueError, FileNotFoundError) as exc:
        _save_failed_state(db, document, str(exc) or "The document could not be parsed.")
        raise HTTPException(status_code=400, detail="The document could not be processed; its failed status was saved.") from exc
    except Exception as exc:
        _save_failed_state(db, document, "Unable to process the document.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process the document; its failed status was saved.",
        ) from exc

    return _persist_extraction(db, document, result)


async def _process_upload(file: UploadFile, consultation_id: UUID, db: Session, user: User) -> dict[str, Any]:
    try:
        # Check authorization before reading or storing any patient document.
        require_consultation_access(db, consultation_id, user)
        filename = Path(file.filename or "").name
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only PDF, PNG, JPG, and JPEG files are supported.")
        if not filename or len(filename) > 255:
            raise HTTPException(status_code=400, detail="Filename must be between 1 and 255 characters.")

        content = await file.read(MAX_FILE_SIZE + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File size must not exceed 10 MB.")

        document = MedicalDocument(
            consultation_id=consultation_id,
            uploaded_by_user_id=user.id,
            filename=filename,
            file_extension=suffix,
            mime_type=file.content_type,
            file_size_bytes=len(content),
            file_content=content,
            processing_status="processing",
            extracted_text="",
            entities=[],
            verification_status="unverified",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            result = _extract_bytes(content, suffix, filename)
        except (ValueError, FileNotFoundError) as exc:
            _save_failed_state(db, document, str(exc) or "The document could not be parsed.")
            raise HTTPException(
                status_code=400,
                detail="The document was stored but could not be processed; its failed status was saved.",
            ) from exc
        except Exception as exc:
            _save_failed_state(db, document, "Unable to process the uploaded document.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The document was stored but processing failed; its failed status was saved.",
            ) from exc

        return _persist_extraction(db, document, result)
    finally:
        await file.close()


@router.post("/documents/upload")
async def upload_medical_document(
    consultation_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compatibility upload route; persist the original file and extraction."""
    return await _process_upload(file, consultation_id, db, current_user)


@router.post("/consultations/{consultation_id}/documents")
async def upload_consultation_document(
    consultation_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document using the consultation API contract."""
    return await _process_upload(file, consultation_id, db, current_user)


@router.get("/consultations/{consultation_id}/documents")
def list_consultation_documents(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List stored documents for a consultation the current user may access."""
    require_consultation_access(db, consultation_id, current_user)
    documents = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.consultation_id == consultation_id)
        .order_by(MedicalDocument.created_at.desc())
        .all()
    )
    return {
        "consultation_id": str(consultation_id),
        "count": len(documents),
        "documents": [_document_response(document) for document in documents],
    }


@router.get("/documents/{document_id}")
def get_medical_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve stored metadata and extraction output, not the binary file."""
    document = db.query(MedicalDocument).filter(MedicalDocument.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Medical document not found.")
    require_consultation_access(db, document.consultation_id, current_user)
    return _document_response(document)


@router.post("/documents/{document_id}/process")
def process_stored_medical_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run OCR/text extraction against the stored original file."""
    document = db.query(MedicalDocument).filter(MedicalDocument.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Medical document not found.")
    require_consultation_access(db, document.consultation_id, current_user)
    return _reprocess_document(db, document)
