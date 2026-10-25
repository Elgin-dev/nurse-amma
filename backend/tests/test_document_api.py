from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Consultation, MedicalDocument, Patient, User  # noqa: F401 - register models
import app.routers.documents as documents_router


TEST_JWT_SECRET = "test-only-jwt-secret-for-document-tests-2026"
TEST_BOOTSTRAP_TOKEN = "test-only-bootstrap-token-document-tests-2026"
TEST_ADMIN_EMAIL = "admin.document-tests@nurseamma.test"
TEST_ADMIN_PASSWORD = "a-secure-document-test-password-123"


@pytest.fixture
def client(monkeypatch) -> Generator[TestClient, None, None]:
    """Isolated SQLite API client with a real authenticated administrator."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    testing_session_local = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    monkeypatch.setattr(settings, "jwt_secret_key", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "bootstrap_admin_token", TEST_BOOTSTRAP_TOKEN)
    monkeypatch.setattr(settings, "access_token_expire_minutes", 60)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            bootstrap_response = test_client.post(
                "/api/v1/auth/bootstrap",
                headers={"X-Bootstrap-Token": TEST_BOOTSTRAP_TOKEN},
                json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            )
            assert bootstrap_response.status_code == 201, bootstrap_response.text

            login_response = test_client.post(
                "/api/v1/auth/login",
                json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            )
            assert login_response.status_code == 200, login_response.text
            token = login_response.json()["access_token"]
            test_client.headers.update({"Authorization": f"Bearer {token}"})
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def _create_consultation(client: TestClient) -> str:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": f"Document Test Patient {uuid4().hex[:8]}"},
    )
    assert patient_response.status_code == 201, patient_response.text
    patient_id = patient_response.json()["id"]

    consultation_response = client.post(
        "/api/v1/consultations",
        json={"patient_id": patient_id, "language": "en"},
    )
    assert consultation_response.status_code == 201, consultation_response.text
    return consultation_response.json()["id"]


def _fake_extraction(text: str, method: str = "Test extraction"):
    def _extract(content: bytes, suffix: str, filename: str) -> dict:
        assert content
        assert suffix in {".pdf", ".png", ".jpg", ".jpeg"}
        return {
            "filename": filename,
            "text": text,
            "entities": [
                {
                    "entity_type": "lab_result",
                    "name": "Hemoglobin",
                    "value": "13.2",
                    "unit": "g/dL",
                    "verification_status": "unverified",
                }
            ],
            "page_count": 1,
            "extraction_method": method,
            "verification_status": "unverified",
        }

    return _extract


def _upload_pdf(client: TestClient, consultation_id: str, content: bytes = b"%PDF-test-content"):
    return client.post(
        f"/api/v1/consultations/{consultation_id}/documents",
        files={"file": ("blood-report.pdf", content, "application/pdf")},
    )


def test_upload_persists_document_and_extraction_and_supports_retrieval(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        documents_router, "_extract_bytes", _fake_extraction("Hemoglobin: 13.2 g/dL")
    )
    consultation_id = _create_consultation(client)

    upload = _upload_pdf(client, consultation_id)
    assert upload.status_code == 200, upload.text
    uploaded = upload.json()
    document_id = uploaded["id"]

    assert uploaded["consultation_id"] == consultation_id
    assert uploaded["filename"] == "blood-report.pdf"
    assert uploaded["file_extension"] == ".pdf"
    assert uploaded["file_size_bytes"] == len(b"%PDF-test-content")
    assert uploaded["processing_status"] == "completed"
    assert uploaded["text"] == "Hemoglobin: 13.2 g/dL"
    assert uploaded["entities"][0]["name"] == "Hemoglobin"
    assert uploaded["verification_status"] == "unverified"
    assert "file_content" not in uploaded

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["text"] == "Hemoglobin: 13.2 g/dL"
    assert "file_content" not in get_response.json()

    list_response = client.get(f"/api/v1/consultations/{consultation_id}/documents")
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert listed["count"] == 1
    assert listed["documents"][0]["id"] == document_id
    assert listed["documents"][0]["filename"] == "blood-report.pdf"


def test_reprocess_uses_persisted_original_bytes_and_updates_result(
    client: TestClient, monkeypatch
) -> None:
    consultation_id = _create_consultation(client)
    original_bytes = b"%PDF-original-bytes-for-reprocessing"
    monkeypatch.setattr(
        documents_router, "_extract_bytes", _fake_extraction("First extraction")
    )
    upload = _upload_pdf(client, consultation_id, original_bytes)
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["id"]

    observed: dict[str, object] = {}

    def reprocess(content: bytes, suffix: str, filename: str) -> dict:
        observed["content"] = content
        observed["suffix"] = suffix
        observed["filename"] = filename
        return {
            "filename": filename,
            "text": "Updated extraction after reprocessing",
            "entities": [],
            "page_count": 2,
            "extraction_method": "Reprocessed test extraction",
            "verification_status": "unverified",
        }

    monkeypatch.setattr(documents_router, "_extract_bytes", reprocess)
    response = client.post(f"/api/v1/documents/{document_id}/process")
    assert response.status_code == 200, response.text
    assert observed == {
        "content": original_bytes,
        "suffix": ".pdf",
        "filename": "blood-report.pdf",
    }
    assert response.json()["processing_status"] == "completed"
    assert response.json()["text"] == "Updated extraction after reprocessing"
    assert response.json()["page_count"] == 2


def test_failed_extraction_is_saved_and_visible_in_consultation_list(
    client: TestClient, monkeypatch
) -> None:
    consultation_id = _create_consultation(client)

    def fail_extraction(content: bytes, suffix: str, filename: str) -> dict:
        raise ValueError("Invalid test document")

    monkeypatch.setattr(documents_router, "_extract_bytes", fail_extraction)
    upload = _upload_pdf(client, consultation_id)
    assert upload.status_code == 400, upload.text

    list_response = client.get(f"/api/v1/consultations/{consultation_id}/documents")
    assert list_response.status_code == 200, list_response.text
    listing = list_response.json()
    assert listing["count"] == 1
    document = listing["documents"][0]
    assert document["filename"] == "blood-report.pdf"
    assert document["processing_status"] == "failed"
    assert document["error_message"] == "Invalid test document"
    assert document["file_size_bytes"] == len(b"%PDF-test-content")


def test_clinician_cannot_read_or_reprocess_another_users_document(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        documents_router, "_extract_bytes", _fake_extraction("Private clinical report")
    )
    consultation_id = _create_consultation(client)
    upload = _upload_pdf(client, consultation_id)
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["id"]

    clinician_email = "clinician.document-tests@nurseamma.test"
    clinician_password = "a-secure-clinician-password-456"
    create_response = client.post(
        "/api/v1/auth/users",
        json={"email": clinician_email, "password": clinician_password},
    )
    assert create_response.status_code == 201, create_response.text

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": clinician_email, "password": clinician_password},
    )
    assert login_response.status_code == 200, login_response.text
    clinician_token = login_response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {clinician_token}"})

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404

    list_response = client.get(f"/api/v1/consultations/{consultation_id}/documents")
    assert list_response.status_code == 404

    process_response = client.post(f"/api/v1/documents/{document_id}/process")
    assert process_response.status_code == 404

    upload_response = client.post(
        f"/api/v1/consultations/{consultation_id}/documents",
        files={"file": ("unauthorized.pdf", b"%PDF-unauthorized", "application/pdf")},
    )
    assert upload_response.status_code == 404

    # Restore admin credentials and prove the denied upload created no extra row.
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200, admin_login.text
    client.headers.update(
        {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    )
    final_list = client.get(f"/api/v1/consultations/{consultation_id}/documents")
    assert final_list.status_code == 200, final_list.text
    assert final_list.json()["count"] == 1
