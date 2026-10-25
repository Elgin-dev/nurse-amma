from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.document_service import process_medical_document
from app.services.ocr_service import extract_image_text
from app.services.entity_extraction import extract_laboratory_entities

router = APIRouter(prefix="/documents", tags=["Medical Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload_medical_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, PNG, JPG, and JPEG files are supported.")

    content = await file.read()

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
                result["entities"] = extract_laboratory_entities(
                    text=result["text"],
                    page_number=1,
                )

            return result

    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to process the uploaded document.") from exc
