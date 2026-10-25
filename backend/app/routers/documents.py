from pathlib import Path
import tempfile
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_consultation_access
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.document_service import process_medical_document
from app.services.entity_extraction import extract_laboratory_entities
from app.services.ocr_service import extract_image_text


router = APIRouter(tags=["Medical Documents"])
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024


async def _process_upload(file: UploadFile, consultation_id: UUID, db: Session, user: User) -> dict:
    try:
        require_consultation_access(db, consultation_id, user)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only PDF, PNG, JPG, and JPEG files are supported.")

        content = await file.read(MAX_FILE_SIZE + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File size must not exceed 10 MB.")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = Path(temp_dir) / f"upload{suffix}"
                file_path.write_bytes(content)
                if suffix == ".pdf":
                    result = process_medical_document(str(file_path))
                    result["extraction_method"] = "PDF text extraction"
                else:
                    result = extract_image_text(str(file_path))
                    result["entities"] = extract_laboratory_entities(text=result["text"], page_number=1)
                result["consultation_id"] = str(consultation_id)
                result["processing_status"] = "completed"
                # This endpoint currently returns extraction output only; durable document
                # records and processing status are handled in the document-persistence phase.
                return result
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to process the uploaded document.",
            ) from exc
    finally:
        await file.close()


@router.post("/documents/upload")
async def upload_medical_document(
    consultation_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compatibility upload route; requires an authorized consultation."""
    return await _process_upload(file, consultation_id, db, current_user)


@router.post("/consultations/{consultation_id}/documents")
async def upload_consultation_document(
    consultation_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document using the shared consultation API contract."""
    return await _process_upload(file, consultation_id, db, current_user)
