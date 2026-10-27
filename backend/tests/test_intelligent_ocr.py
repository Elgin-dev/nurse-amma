from collections.abc import Generator
from io import BytesIO
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import httpx
import pytest

from app.core.security import get_current_user
from app.db.session import get_db
from app.main import app
from app.services import ocr_service
from app.services import intelligent_ocr_service
from app.services.intelligent_ocr_service import IntelligentOCRService
from app.core.config import settings

class FakeHTTPResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": json.dumps(self.data)}}


def test_extract_image_text_from_bytes_uses_tesseract(monkeypatch):
    image_buffer = BytesIO()
    Image.new("RGB", (4, 4), "white").save(image_buffer, format="PNG")
    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_string",
        lambda _image: "Hemoglobin: 12 g/dL",
    )

    result = ocr_service.extract_image_text_from_bytes(image_buffer.getvalue())

    assert result["text"] == "Hemoglobin: 12 g/dL"
    assert result["extraction_method"] == "OCR"
    assert result["verification_status"] == "unverified"


def test_intelligent_ocr_structures_ocr_text_with_ollama(monkeypatch):
    raw_text = (
        "Patient Name: Sam Example\nAge: 42\nGender: Female\n"
        "Hemoglobin: 10.2 g/dL (range 12-16) low\n"
        "Medication: Iron 200 mg twice daily\nDiagnosis: Anemia"
    )
    expected = {
        "cleaned_text": raw_text,
        "patient_demographics": {
            "name": "Sam Example",
            "age": 42,
            "gender": None,
        },
        "prescribed_medications": [
            {"drug_name": "Iron", "dosage": "200 mg", "frequency": "twice daily"}
        ],
        "lab_results": [
            {
                "test_name": "Hemoglobin",
                "value": "10.2 g/dL",
                "unit": None,
                "reference_range": "12-16",
                "abnormality_flag": True,
            }
        ],
        "clinical_diagnosis": ["Anemia"],
        "doctor_notes": None,
    }
    captured = {}

    def fake_ocr(image_bytes):
        return {"text": raw_text, "extraction_method": "OCR"}

    def fake_post(url, *, json, timeout):
        captured.update({"url": url, "request": json, "timeout": timeout})
        return FakeHTTPResponse(expected)

    monkeypatch.setattr(
        intelligent_ocr_service,
        "extract_image_text_from_bytes",
        fake_ocr,
    )
    monkeypatch.setattr(intelligent_ocr_service.httpx, "post", fake_post)

    result = IntelligentOCRService.process_image(b"image bytes", "report.png")

    assert result["structuring_source"] == "ollama"
    assert result["raw_ocr_text"] == raw_text
    assert result["structured_data"]["patient_demographics"]["name"] == "Sam Example"
    assert result["structured_data"]["patient_demographics"]["age"] == "42"
    assert result["structured_data"]["patient_demographics"]["gender"] == "Female"
    assert result["structured_data"]["lab_results"][0]["value"] == "10.2"
    assert result["structured_data"]["lab_results"][0]["unit"] == "g/dL"
    assert result["structured_data"]["lab_results"][0]["abnormality_flag"] is True
    assert captured["url"] == settings.ollama_chat_url
    assert captured["request"]["model"] == settings.ollama_model
    assert captured["request"]["format"] == "json"
    assert raw_text in captured["request"]["messages"][-1]["content"]


def test_intelligent_ocr_falls_back_when_ollama_is_unreachable(monkeypatch):
    raw_text = (
        "Patient Name: Sam Example\nAge: 42\nGender: Female\n"
        "Hemoglobin: 10.2 g/dL (range 12-16) low\n"
        "Medication: Iron 200 mg twice daily\nDiagnosis: Anemia"
    )

    def fake_ocr(image_bytes):
        return {"text": raw_text, "extraction_method": "OCR"}

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Ollama is unavailable")

    monkeypatch.setattr(
        intelligent_ocr_service,
        "extract_image_text_from_bytes",
        fake_ocr,
    )
    monkeypatch.setattr(intelligent_ocr_service.httpx, "post", unavailable)

    result = IntelligentOCRService.process_image(b"image bytes", "report.png")

    assert result["structuring_source"] == "offline"
    assert result["structured_data"]["patient_demographics"]["name"] == "Sam Example"
    assert result["structured_data"]["clinical_diagnosis"] == ["Anemia"]
    assert result["structured_data"]["lab_results"][0]["test_name"] == "Hemoglobin"
    assert result["verification_status"] == "unverified"


@pytest.fixture
def document_client(monkeypatch) -> Generator[TestClient, None, None]:
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: object()

    def allow_consultation_access(_db, _consultation_id, _user):
        return None

    monkeypatch.setattr(
        "app.routers.clinical_history.require_consultation_access",
        allow_consultation_access,
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_process_document_endpoint_accepts_image_and_returns_structured_data(
    document_client,
    monkeypatch,
):
    consultation_id = str(uuid4())
    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    ocr_text = "Patient Name: Sam Example\nAge: 42\nGender: Female"
    expected = {
        "cleaned_text": ocr_text,
        "patient_demographics": {
            "name": "Sam Example",
            "age": "42",
            "gender": "Female",
        },
        "prescribed_medications": [],
        "lab_results": [],
        "clinical_diagnosis": [],
        "doctor_notes": None,
    }

    monkeypatch.setattr(
        intelligent_ocr_service,
        "extract_image_text_from_bytes",
        lambda _image_bytes: {
            "text": ocr_text,
            "extraction_method": "OCR",
        },
    )
    monkeypatch.setattr(
        intelligent_ocr_service.httpx,
        "post",
        lambda *args, **kwargs: FakeHTTPResponse(expected),
    )

    response = document_client.post(
        f"/api/v1/consultations/{consultation_id}/process-document",
        files={"file": ("patient.png", image_bytes, "image/png")},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["filename"] == "patient.png"
    assert result["structuring_source"] == "ollama"
    assert result["structured_data"]["patient_demographics"]["age"] == "42"


def test_process_document_endpoint_rejects_non_image_file(document_client):
    consultation_id = str(uuid4())
    response = document_client.post(
        f"/api/v1/consultations/{consultation_id}/process-document",
        files={"file": ("report.pdf", b"%PDF-1.7 fake", "application/pdf")},
    )

    assert response.status_code == 400
