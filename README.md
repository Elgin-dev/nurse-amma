
# Nurse Amma 🩺
## AI-Powered Healthcare Assistant

Nurse Amma is an AI-powered healthcare project designed to support medical document processing and information extraction. The Medical Document Intelligence module extracts text from medical PDFs and images, then identifies laboratory test results in a structured format.

## Features

- **PDF Text Extraction:** Extracts text from digital medical PDF documents page by page.
- **OCR Processing:** Extracts text from medical document images using Tesseract OCR.
- **Laboratory Entity Extraction:** Identifies laboratory test names, values, and units from extracted text.
- **Source Tracking:** Records the source page and text associated with extracted information.
- **Verification Status:** Marks extracted results as `unverified` so they can be reviewed before clinical use.
- **REST API:** Provides a FastAPI endpoint for uploading medical documents.
- **Unit Testing:** Includes tests for document processing, entity extraction, and OCR.

## Technology Stack

- Python
- FastAPI
- PyMuPDF
- Tesseract OCR
- pytesseract
- Pillow
- pytest

## Project Structure

```text
backend/
├── app/
│   ├── routers/
│   │   └── documents.py
│   └── services/
│       ├── pdf_service.py
│       ├── ocr_service.py
│       ├── entity_extraction.py
│       └── document_service.py
└── tests/
    ├── test_document_service.py
    ├── test_entity_extraction.py
    └── test_ocr_service.py
```

## Requirements

- Python 3.10 or a compatible version supported by the project
- Tesseract OCR installed on the system
- Python dependencies listed in the backend requirements file

### Install Tesseract OCR on Windows

Install Tesseract OCR and ensure the executable is available. If needed, configure its path in `ocr_service.py`.

Example installation path:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Setup and Installation

Open PowerShell and navigate to the backend directory:

```powershell
cd backend
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
pip install -r requirements.txt
```

If the required packages are not already included in `requirements.txt`, install the relevant dependencies:

```powershell
pip install fastapi uvicorn pymupdf pytesseract pillow python-multipart pytest
```

## Running the Application

From the backend directory, start the FastAPI application:

```powershell
uvicorn app.main:app --reload
```

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

The document upload endpoint is:

```http
POST /documents/upload
```

Supported file formats:

- PDF
- PNG
- JPG
- JPEG

Maximum upload size: 10 MB.

## API Usage

Use the Swagger UI at `/docs` to test the document upload endpoint.

1. Open the API documentation.
2. Find `POST /documents/upload`.
3. Select **Try it out**.
4. Upload a supported medical document.
5. Execute the request.
6. Review the extracted text and laboratory entities in the response.

## Extracted Information

The extraction pipeline can identify laboratory results such as glucose, hemoglobin, and creatinine when they appear in supported text formats.

Extracted entities may include:

- Laboratory test name
- Result value
- Unit
- Source page number
- Source text
- Verification status

Example response fragment:

```json
{
  "entities": [
    {
      "test_name": "Glucose",
      "value": "95",
      "unit": "mg/dL",
      "source_page": 1,
      "verification_status": "unverified"
    }
  ]
}
```

The exact response structure depends on the API implementation and the document content.

## Running Tests

From the backend directory:

```powershell
python -m pytest tests/test_document_service.py tests/test_entity_extraction.py tests/test_ocr_service.py -v
```

These tests cover document text extraction, laboratory entity extraction, and OCR functionality.

## Medical Safety and Limitations

- Extracted information is not a medical diagnosis.
- OCR and text extraction may produce incomplete or incorrect results.
- Laboratory entities are marked as `unverified`.
- A qualified healthcare professional should verify extracted results before clinical use.
- Scanned PDFs may require a separate OCR pipeline if they contain no selectable text.
- The current entity extraction logic uses pattern-based processing and may not support every laboratory report format.

## Team Contribution

The Medical Document Intelligence module covers:

- PDF text extraction
- OCR-based image text extraction
- Laboratory result entity extraction
- Document upload API
- Automated tests for the module

## Future Enhancements

- OCR support for scanned PDFs
- Support for additional laboratory tests and document formats
- Improved entity extraction using clinical NLP models
- Confidence scoring and human verification workflows
- Secure document storage and access control
- Integration with other Nurse Amma healthcare modules

## Disclaimer

Nurse Amma is a software project for healthcare assistance and document processing. Extracted results should not be used for clinical decisions without appropriate professional verification.
## Backend Authentication and Document Upload Setup

The application reads `.env` from the repository root. Never commit this file or share its secrets.

Required settings: `DATABASE_URL`, `JWT_SECRET_KEY`, and `BOOTSTRAP_ADMIN_TOKEN`. `ACCESS_TOKEN_EXPIRE_MINUTES` is optional and defaults to 60.

Generate cryptographically random secrets locally using Python `secrets.token_urlsafe`. Add the generated values to the root `.env` file. Never put real secret values in documentation.

Create the initial administrator using `POST /api/v1/auth/bootstrap` with the `X-Bootstrap-Token` header. Authenticate using `POST /api/v1/auth/login` and the returned bearer token.

The consultation document endpoint is `POST /api/v1/consultations/{consultation_id}/documents`. The compatibility endpoint `POST /api/v1/documents/upload` accepts file-only requests for extraction without persistence; adding `consultation_id` enables persistence.

PDF, PNG, JPG, and JPEG uploads are limited to 10 MB and must match their declared file type. Extracted laboratory results remain `unverified` until reviewed through an authorized clinical workflow.
