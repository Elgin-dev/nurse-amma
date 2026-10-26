from collections.abc import Generator
from time import sleep
from uuid import UUID, uuid4

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User
import app.routers.documents as documents_router


@pytest.fixture
def testing_session_local():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def client(testing_session_local) -> Generator[TestClient, None, None]:
    """Authenticated client; the admin identity is injected via dependency override."""

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    admin_id = uuid4()
    with testing_session_local() as db:
        db.add(
            User(
                id=admin_id,
                email="timeline-admin@nurseamma.test",
                password_hash="unused-in-this-dependency-override",
                role="admin",
                is_active=True,
            )
        )
        db.commit()

    def override_current_user():
        with testing_session_local() as db:
            return db.get(User, admin_id)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def no_auth_client(testing_session_local) -> Generator[TestClient, None, None]:
    """Client that exercises the real Bearer auth dependency (no identity override)."""

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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def create_consultation(client: TestClient) -> str:
    patient_response = client.post(
        "/api/v1/patients",
        json={"consent_confirmed": True, "full_name": "Timeline Test Patient"},
    )
    assert patient_response.status_code == 201, patient_response.text
    patient_id = patient_response.json()["id"]

    consultation_response = client.post(
        "/api/v1/consultations",
        json={"patient_id": patient_id, "language": "en"},
    )
    assert consultation_response.status_code == 201, consultation_response.text
    return consultation_response.json()["id"]


def history_payload(consultation_id: str) -> dict:
    return {
        "consultation_id": consultation_id,
        "chief_complaint": "fever",
        "symptom_details": {
            "duration": {"value": 4, "unit": "days"},
            "severity": "moderate",
        },
        "associated_symptoms": ["Altered Sensorium"],
        "past_medical_history": [],
        "current_medications": ["Medication A"],
        "allergies": [],
        "source": "patient_reported",
    }


def _fake_extraction(text: str = "Synthetic laboratory result"):
    def _extract(content: bytes, suffix: str, filename: str) -> dict:
        return {
            "filename": filename,
            "text": text,
            "entities": [
                {
                    "entity_type": "laboratory_result",
                    "name": "Hemoglobin",
                    "value": "13.2",
                    "unit": "g/dL",
                    "verification_status": "unverified",
                }
            ],
            "page_count": 1,
            "extraction_method": "Test extraction",
            "verification_status": "unverified",
        }

    return _extract


def _valid_pdf_bytes(text: str = "Synthetic test report") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def test_timeline_returns_derived_events_in_order(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        documents_router, "_extract_bytes", _fake_extraction()
    )

    consultation_id = create_consultation(client)

    history = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=history_payload(consultation_id),
    )
    assert history.status_code == 201, history.text
    sleep(0.02)

    summary = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json=history_payload(consultation_id),
    )
    assert summary.status_code == 200, summary.text
    sleep(0.02)

    upload = client.post(
        f"/api/v1/consultations/{consultation_id}/documents",
        files={"file": ("synthetic-report.pdf", _valid_pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    response = client.get(f"/api/v1/consultations/{consultation_id}/timeline")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["consultation_id"] == consultation_id
    assert body["count"] == len(body["events"])
    assert body["count"] >= 4

    event_types = [event["event_type"] for event in body["events"]]
    assert "clinical_history_submitted" in event_types
    assert "summary_generated" in event_types
    assert "red_flag_recorded" in event_types
    assert "document_uploaded" in event_types
    assert "document_processed" in event_types

    timestamps = [event["occurred_at"] for event in body["events"]]
    assert timestamps == sorted(timestamps)

    history_event = next(
        event for event in body["events"]
        if event["event_type"] == "clinical_history_submitted"
    )
    assert history_event["source"] == "patient_reported"
    assert history_event["status"] == "unverified"
    assert UUID(history_event["related_entity_id"])

    summary_event = next(
        event for event in body["events"]
        if event["event_type"] == "summary_generated"
    )
    assert summary_event["source"] == "generated_summary"
    assert summary_event["status"] == "pending_doctor_approval"

    flag_event = next(
        event for event in body["events"]
        if event["event_type"] == "red_flag_recorded"
    )
    assert flag_event["source"] == "rule_based_red_flag"
    assert flag_event["status"] == "pending_review"

    doc_event = next(
        event for event in body["events"]
        if event["event_type"] == "document_processed"
    )
    assert doc_event["source"] == "document_extracted"
    assert doc_event["status"] == "unverified"


def test_timeline_does_not_leak_another_consultation(client: TestClient):
    first_consultation_id = create_consultation(client)
    first_history = client.post(
        f"/api/v1/consultations/{first_consultation_id}/responses",
        json=history_payload(first_consultation_id),
    )
    assert first_history.status_code == 201, first_history.text

    second_consultation_id = create_consultation(client)
    second_history = client.post(
        f"/api/v1/consultations/{second_consultation_id}/responses",
        json=history_payload(second_consultation_id),
    )
    assert second_history.status_code == 201, second_history.text

    first_timeline = client.get(
        f"/api/v1/consultations/{first_consultation_id}/timeline"
    ).json()
    second_timeline = client.get(
        f"/api/v1/consultations/{second_consultation_id}/timeline"
    ).json()

    first_ids = {event["event_id"] for event in first_timeline["events"]}
    second_ids = {event["event_id"] for event in second_timeline["events"]}
    assert first_ids.isdisjoint(second_ids)


def test_timeline_requires_authentication(no_auth_client: TestClient):
    response = no_auth_client.get(
        f"/api/v1/consultations/{uuid4()}/timeline"
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_timeline_returns_404_for_missing_consultation(client: TestClient):
    response = client.get(f"/api/v1/consultations/{uuid4()}/timeline")
    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"


def test_timeline_returns_empty_events_for_consultation_with_no_activity(
    client: TestClient,
):
    consultation_id = create_consultation(client)
    response = client.get(f"/api/v1/consultations/{consultation_id}/timeline")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["events"] == []
    assert body["count"] == 0