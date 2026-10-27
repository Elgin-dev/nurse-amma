from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID

import pymupdf
from PIL import Image
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.medical_document import MedicalDocument
from app.models.user import User
from app.services.intelligent_ocr_service import IntelligentOCRService


router = APIRouter(tags=["Medical Documents"])
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024
EXPECTED_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
GENERIC_CONTENT_TYPES = {"", "application/octet-stream"}


def _validate_file_signature(content: bytes, suffix: str) -> bool:
    """Check the signature and openability before persisting uploaded bytes."""
    if suffix == ".pdf":
        if b"%PDF-" not in content[:1024]:
            return False
        try:
            with pymupdf.open(stream=content, filetype="pdf") as document:
                return document.page_count > 0
        except Exception:
            return False

    expected_header = {
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }.get(suffix)
    if expected_header is None or not content.startswith(expected_header):
        return False

    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            image.verify()
    except Exception:
        return False

    if suffix == ".png":
        return image_format == "PNG"
    return image_format == "JPEG"


def _validate_declared_content_type(suffix: str, content_type: str | None) -> None:
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if declared in GENERIC_CONTENT_TYPES:
        return
    if declared != EXPECTED_CONTENT_TYPES[suffix]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The declared content type does not match the file extension.",
        )


def _mark_entities_unverified(entities: Any) -> list[dict[str, Any]]:
    """Never let the extraction layer assert clinician verification."""
    if not isinstance(entities, list):
        return []
    return [
        {**entity, "verification_status": "unverified"}
        for entity in entities
        if isinstance(entity, dict)
    ]


async def _read_and_validate_upload(file: UploadFile) -> tuple[str, str, bytes]:
    raw_filename = (file.filename or "").strip().replace("\\", "/")
    filename = Path(raw_filename).name
    if not filename or len(filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must be between 1 and 255 characters.",
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, PNG, JPG, and JPEG files are supported.",
        )

    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File size must not exceed 10 MB.",
        )

    _validate_declared_content_type(suffix, file.content_type)
    if not _validate_file_signature(content, suffix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a supported file format.",
        )

    return filename, suffix, content


def _extract_bytes(content: bytes, suffix: str, original_filename: str) -> dict[str, Any]:
    """Use the AI Intelligent OCR service for both PDFs and Images."""
    if suffix == ".pdf":
        result = IntelligentOCRService.process_pdf(content, original_filename)
    else:
        result = IntelligentOCRService.process_image(content, original_filename)
        
    structured_data = result.get("structured_data", {})
    
    # Ensure the AI results are marked unverified
    if structured_data:
        structured_data["verification_status"] = "unverified"
        
    # The frontend UI expects entities to be a list containing the structured dict
    entities = [structured_data] if structured_data else []
    
    return {
        "filename": original_filename,
        "text": result.get("raw_ocr_text", ""),
        "entities": _mark_entities_unverified(entities),
        "page_count": result.get("page_count", 1),
        "extraction_method": result.get("extraction_method", "AI Intelligent OCR"),
        "verification_status": "unverified",
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
        "verified_by_user_id": (
            str(document.verified_by_user_id) if document.verified_by_user_id else None
        ),
        "verified_at": document.verified_at,
        "verification_notes": document.verification_notes,
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


def _persist_extraction(
    db: Session, document: MedicalDocument, result: dict[str, Any]
) -> dict[str, Any]:
    document.extracted_text = result.get("text", "")
    document.entities = _mark_entities_unverified(result.get("entities", []))
    document.page_count = result.get("page_count", 1)
    document.extraction_method = result.get("extraction_method", "unknown")
    document.verification_status = "unverified"
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
        result = _extract_bytes(
            document.file_content, document.file_extension, document.filename
        )
    except (ValueError, FileNotFoundError) as exc:
        _save_failed_state(db, document, "The document could not be parsed or is invalid.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The document could not be processed; its failed status was saved.",
        ) from exc
    except Exception as exc:
        _save_failed_state(db, document, "Unable to process the document.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process the document; its failed status was saved.",
        ) from exc

    return _persist_extraction(db, document, result)


async def _process_upload(
    file: UploadFile, consultation_id: UUID, db: Session, user: User
) -> dict[str, Any]:
    try:
        require_consultation_access(db, consultation_id, user)
        filename, suffix, content = await _read_and_validate_upload(file)

        document = MedicalDocument(
            consultation_id=consultation_id,
            uploaded_by_user_id=user.id,
            filename=filename,
            file_extension=suffix,
            mime_type=(file.content_type or EXPECTED_CONTENT_TYPES[suffix]),
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
            _save_failed_state(db, document, "The document could not be parsed or is invalid.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
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
    file: UploadFile = File(...),
    consultation_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if consultation_id is not None:
        return await _process_upload(file, consultation_id, db, current_user)

    try:
        filename, suffix, content = await _read_and_validate_upload(file)
        try:
            return _extract_bytes(content, suffix, filename)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to process the uploaded document.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to process the uploaded document.",
            ) from exc
    finally:
        await file.close()


@router.post("/consultations/{consultation_id}/documents")
async def upload_consultation_document(
    consultation_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _process_upload(file, consultation_id, db, current_user)


@router.get("/consultations/{consultation_id}/documents")
def list_consultation_documents(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    document = db.query(MedicalDocument).filter(MedicalDocument.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Medical document not found.")
    require_consultation_access(db, document.consultation_id, current_user)
    return _reprocess_document(db, document)