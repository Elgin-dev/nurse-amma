from collections.abc import Generator
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


def _create_user(db_factory, role: str, email: str) -> UUID:
    user_id = uuid4()
    with db_factory() as db:
        db.add(
            User(
                id=user_id,
                email=email,
                password_hash="unused-in-this-dependency-override",
                role=role,
                is_active=True,
            )
        )
        db.commit()
    return user_id


@pytest.fixture
def admin_id(testing_session_local):
    return _create_user(
        testing_session_local, "admin", "review-admin@nurseamma.test"
    )


@pytest.fixture
def clinician_id(testing_session_local):
    return _create_user(
        testing_session_local, "clinician", "review-clinician@nurseamma.test"
    )


@pytest.fixture
def other_clinician_id(testing_session_local):
    return _create_user(
        testing_session_local, "clinician", "review-other@nurseamma.test"
    )


@pytest.fixture
def client(testing_session_local) -> Generator[TestClient, None, None]:
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


def set_current_user(testing_session_local, user_id):
    def override_current_user():
        with testing_session_local() as db:
            return db.get(User, user_id)
    app.dependency_overrides[get_current_user] = override_current_user


def _create_consultation_as(client: TestClient, testing_session_local, user_id) -> str:
    set_current_user(testing_session_local, user_id)
    patient_response = client.post(
        "/api/v1/patients",
        json={"consent_confirmed": True, "full_name": "Review Test Patient"},
    )
    assert patient_response.status_code == 201, patient_response.text
    patient_id = patient_response.json()["id"]

    consultation_response = client.post(
        "/api/v1/consultations",
        json={"patient_id": patient_id, "language": "en"},
    )
    assert consultation_response.status_code == 201, consultation_response.text
    return consultation_response.json()["id"]


def _save_history(client: TestClient, consultation_id: str) -> None:
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json={
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
        },
    )
    assert response.status_code == 201, response.text


def _generate_summary(client: TestClient, consultation_id: str) -> dict:
    response = client.post(f"/api/v1/consultations/{consultation_id}/summary")
    assert response.status_code == 200, response.text
    return response.json()


def _setup_summary(client: TestClient, testing_session_local, user_id) -> tuple[str, dict]:
    consultation_id = _create_consultation_as(client, testing_session_local, user_id)
    set_current_user(testing_session_local, user_id)
    _save_history(client, consultation_id)
    summary = _generate_summary(client, consultation_id)
    return consultation_id, summary


def _summary_uuid(summary: dict) -> str:
    return summary["summary_id"].removeprefix("SUM-")


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


def _valid_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Synthetic test report")
    content = document.tobytes()
    document.close()
    return content


def test_summary_review_approve_sets_reviewer_and_timestamp(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    response = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "approved", "notes": "Reviewed by clinician"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_status"] == "approved"
    assert body["reviewed_by_user_id"] == str(clinician_id)
    assert body["review_notes"] == "Reviewed by clinician"
    assert body["reviewed_at"] is not None


def test_summary_review_needs_correction_then_approve(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    first = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "needs_correction"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["review_status"] == "needs_correction"

    second = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "approved"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["review_status"] == "approved"


def test_summary_review_rejects_invalid_transition(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    first = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "approved"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "rejected"},
    )
    assert second.status_code == 409


def test_other_clinician_cannot_review_summary(
    client, testing_session_local, clinician_id, other_clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, other_clinician_id)

    response = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "approved"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"


def test_summary_correction_resets_review_status_and_records_reviewer(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    approved = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "approved"},
    )
    assert approved.status_code == 200

    corrected = client.patch(
        f"/api/v1/summaries/{_summary_uuid(summary)}",
        json={"chief_complaint": "high fever", "notes": "Corrected CC"},
    )
    assert corrected.status_code == 200, corrected.text
    body = corrected.json()
    assert body["chief_complaint"] == "high fever"
    assert body["review_status"] == "pending_doctor_approval"
    assert body["corrected_by_user_id"] == str(clinician_id)
    assert body["corrected_at"] is not None
    # A correction invalidates a prior review.
    assert body["reviewed_by_user_id"] is None
    assert body["reviewed_at"] is None


def test_summary_correction_requires_at_least_one_field(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    response = client.patch(
        f"/api/v1/summaries/{_summary_uuid(summary)}",
        json={"notes": "no fields changed"},
    )
    assert response.status_code == 422


def test_red_flag_review_happy_path(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    assert summary["red_flags"], "Expected at least one red flag for this history"
    flag = summary["red_flags"][0]
    assert flag["id"], "Red flag review requires the persisted flag id"

    set_current_user(testing_session_local, clinician_id)
    response = client.post(
        f"/api/v1/red-flags/{flag['id']}/review",
        json={"status": "acknowledged", "notes": "Acknowledged"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_status"] == "acknowledged"
    assert body["reviewed_by_user_id"] == str(clinician_id)


def test_red_flag_terminal_state_rejects_further_reviews(
    client, testing_session_local, clinician_id,
):
    _, summary = _setup_summary(client, testing_session_local, clinician_id)
    flag = summary["red_flags"][0]

    set_current_user(testing_session_local, clinician_id)
    first = client.post(
        f"/api/v1/red-flags/{flag['id']}/review",
        json={"status": "verified"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/red-flags/{flag['id']}/review",
        json={"status": "acknowledged"},
    )
    assert second.status_code == 409


def test_document_verification_happy_path(
    client, testing_session_local, clinician_id, monkeypatch,
):
    monkeypatch.setattr(documents_router, "_extract_bytes", _fake_extraction())
    consultation_id = _create_consultation_as(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    upload = client.post(
        f"/api/v1/consultations/{consultation_id}/documents",
        files={"file": ("synthetic.pdf", _valid_pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["id"]

    response = client.post(
        f"/api/v1/documents/{document_id}/verify",
        json={"status": "verified", "notes": "Reviewed source"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification_status"] == "verified"
    assert body["verified_by_user_id"] == str(clinician_id)
    assert body["verified_at"] is not None

    # A verified document is terminal; a further transition must fail.
    second = client.post(
        f"/api/v1/documents/{document_id}/verify",
        json={"status": "rejected"},
    )
    assert second.status_code == 409


def test_timeline_includes_review_events(
    client, testing_session_local, clinician_id,
):
    consultation_id, summary = _setup_summary(client, testing_session_local, clinician_id)
    set_current_user(testing_session_local, clinician_id)

    reviewed = client.post(
        f"/api/v1/summaries/{_summary_uuid(summary)}/review",
        json={"status": "approved"},
    )
    assert reviewed.status_code == 200, reviewed.text

    timeline = client.get(f"/api/v1/consultations/{consultation_id}/timeline")
    assert timeline.status_code == 200, timeline.text
    event_types = [event["event_type"] for event in timeline.json()["events"]]
    assert "summary_reviewed" in event_types

    reviewed_event = next(
        event for event in timeline.json()["events"]
        if event["event_type"] == "summary_reviewed"
    )
    assert reviewed_event["source"] == "clinician_verified"
    assert reviewed_event["status"] == "approved"