from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.security import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import ClinicalHistorySubmission, ClinicalRedFlag, ClinicalSummary, User


@pytest.fixture
def testing_session_local():
    """Provide an isolated SQLite database for API tests."""
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
    """Provide an API client using the isolated test database."""
    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    # These endpoint tests use an administrator identity while testing the
    # clinical-history behavior itself. Authentication is tested independently
    # in test_auth_api.py.
    test_admin_id = uuid4()
    with testing_session_local() as db:
        db.add(User(
            id=test_admin_id,
            email="test-admin@nurseamma.test",
            password_hash="unused-in-this-dependency-override",
            role="admin",
            is_active=True,
        ))
        db.commit()

    def override_current_user():
        with testing_session_local() as db:
            return db.get(User, test_admin_id)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def create_consultation(client: TestClient) -> str:
    """Create a synthetic patient and consultation through the API."""
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Integration Test Patient"},
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
    """Return a synthetic structured patient-reported history submission."""
    return {
        "consultation_id": consultation_id,
        "chief_complaint": "fever",
        "symptom_details": {
            "duration": {"value": 4, "unit": "days"},
            "severity": "moderate",
            "progression": "worsening",
        },
        "associated_symptoms": ["body pain"],
        "past_medical_history": [],
        "current_medications": ["Medication A"],
        "allergies": [],
        "source": "patient_reported",
    }


def test_next_question_for_existing_consultation(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/next-question",
        params={"chief_complaint": "fever"},
    )
    assert response.status_code == 200
    assert response.json()["question_key"] == "duration"
    assert response.json()["is_complete"] is False


def test_next_question_returns_404_for_missing_consultation(client: TestClient):
    missing_id = str(uuid4())
    response = client.post(
        f"/api/v1/consultations/{missing_id}/next-question",
        params={"chief_complaint": "fever"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"


def test_summary_rejects_mismatched_consultation_ids(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json={
            "consultation_id": str(uuid4()),
            "chief_complaint": "fever",
            "symptom_details": {},
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "consultation_id in request body must match the URL"


def test_summary_for_existing_consultation(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json={
            "consultation_id": consultation_id,
            "chief_complaint": "fever",
            "symptom_details": {"duration": {"value": 4, "unit": "days"}},
            "associated_symptoms": ["Altered Sensorium"],
            "current_medications": ["Medication A"],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["consultation_id"] == consultation_id
    assert result["summary_id"].startswith("SUM-")
    assert result["review_status"] == "pending_doctor_approval"
    assert len(result["red_flags"]) == 1
    assert result["red_flags"][0]["flag_id"] == "RF-001"
    assert result["red_flags"][0]["review_status"] == "pending_review"
    assert result["medication_history"][0]["status"] == "unverified"


def test_save_history_returns_created_snapshot(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=history_payload(consultation_id),
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert UUID(result["id"])
    assert result["consultation_id"] == consultation_id
    assert result["version"] == 1
    assert result["schema_version"] == 1
    assert result["source"] == "patient_reported"
    assert result["verification_status"] == "unverified"
    assert result["payload"]["chief_complaint"] == "fever"
    assert result["payload"]["current_medications"] == ["Medication A"]
    assert result["created_at"]


def test_saved_history_exists_in_database(client: TestClient, testing_session_local):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=history_payload(consultation_id),
    )
    assert response.status_code == 201, response.text
    saved_id = UUID(response.json()["id"])
    with testing_session_local() as db:
        saved = db.get(ClinicalHistorySubmission, saved_id)
        assert saved is not None
        assert saved.consultation_id == UUID(consultation_id)
        assert saved.version == 1
        assert saved.payload["chief_complaint"] == "fever"


def test_history_submission_versions_increase(client: TestClient, testing_session_local):
    consultation_id = create_consultation(client)
    url = f"/api/v1/consultations/{consultation_id}/responses"
    first_payload = history_payload(consultation_id)
    first = client.post(url, json=first_payload)
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1

    second_payload = history_payload(consultation_id)
    second_payload["symptom_details"]["severity"] = "severe"
    second = client.post(url, json=second_payload)
    assert second.status_code == 201, second.text
    assert second.json()["version"] == 2
    assert second.json()["id"] != first.json()["id"]

    with testing_session_local() as db:
        count = db.scalar(
            select(func.count()).select_from(ClinicalHistorySubmission).where(
                ClinicalHistorySubmission.consultation_id == UUID(consultation_id)
            )
        )
        assert count == 2


def test_history_rejects_mismatched_consultation_ids(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=history_payload(str(uuid4())),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "consultation_id in request body must match the URL"


def test_history_rejects_invalid_body_consultation_id(client: TestClient):
    consultation_id = create_consultation(client)
    payload = history_payload(consultation_id)
    payload["consultation_id"] = "not-a-valid-uuid"
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid consultation_id in request body"


def test_history_returns_404_for_missing_consultation(client: TestClient):
    missing_id = str(uuid4())
    response = client.post(
        f"/api/v1/consultations/{missing_id}/responses",
        json=history_payload(missing_id),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"


def test_caller_cannot_falsify_source_on_history_endpoint(client: TestClient):
    consultation_id = create_consultation(client)
    payload = history_payload(consultation_id)
    payload["source"] = "document"
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=payload,
    )
    assert response.status_code == 422


def test_caller_cannot_falsify_source_on_summary_endpoint(client: TestClient):
    consultation_id = create_consultation(client)
    payload = history_payload(consultation_id)
    payload["source"] = "clinician_verified"
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json=payload,
    )
    assert response.status_code == 422


def test_summary_get_returns_404_when_no_summary_exists(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.get(f"/api/v1/consultations/{consultation_id}/summary")
    assert response.status_code == 404
    assert response.json()["detail"] == "No saved clinical summary found"


def test_summary_get_returns_latest_generated_summary(client: TestClient):
    consultation_id = create_consultation(client)
    url = f"/api/v1/consultations/{consultation_id}/summary"
    first_payload = history_payload(consultation_id)
    first = client.post(url, json=first_payload)
    assert first.status_code == 200, first.text

    second_payload = history_payload(consultation_id)
    second_payload["symptom_details"]["severity"] = "severe"
    second_payload["associated_symptoms"] = ["shortness of breath"]
    second = client.post(url, json=second_payload)
    assert second.status_code == 200, second.text
    assert second.json()["summary_id"] != first.json()["summary_id"]

    retrieved = client.get(url)
    assert retrieved.status_code == 200, retrieved.text
    assert retrieved.json()["summary_id"] == second.json()["summary_id"]
    assert "Severity: severe." in retrieved.json()["history_of_present_illness"]


def test_summary_and_red_flags_are_persisted(client: TestClient, testing_session_local):
    consultation_id = create_consultation(client)
    payload = history_payload(consultation_id)
    payload["associated_symptoms"] = ["Altered Sensorium"]
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json=payload,
    )
    assert response.status_code == 200, response.text
    summary_id = UUID(response.json()["summary_id"].removeprefix("SUM-"))

    with testing_session_local() as db:
        summary = db.get(ClinicalSummary, summary_id)
        assert summary is not None
        flags = db.scalars(
            select(ClinicalRedFlag).where(ClinicalRedFlag.summary_id == summary_id)
        ).all()
        assert len(flags) == 1
        assert flags[0].flag_id == "RF-001"
        assert flags[0].review_status == "pending_review"

    retrieved = client.get(
        f"/api/v1/consultations/{consultation_id}/summary"
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["red_flags"][0]["review_status"] == "pending_review"


def test_clinician_cannot_access_another_clinicians_consultation(
    client: TestClient, testing_session_local,
):
    consultation_id = create_consultation(client)
    clinician_id = uuid4()
    with testing_session_local() as db:
        db.add(User(
            id=clinician_id,
            email="other-clinician@nurseamma.test",
            password_hash="unused-in-this-dependency-override",
            role="clinician",
            is_active=True,
        ))
        db.commit()

    def override_other_clinician():
        with testing_session_local() as db:
            return db.get(User, clinician_id)

    old_dependency = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = override_other_clinician
    try:
        response = client.get(
            f"/api/v1/consultations/{consultation_id}/summary"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Consultation not found"
    finally:
        app.dependency_overrides[get_current_user] = old_dependency


def test_history_rejects_missing_required_fields(client: TestClient):
    consultation_id = create_consultation(client)
    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json={"consultation_id": consultation_id, "chief_complaint": "fever"},
    )
    assert response.status_code == 422
    assert "symptom_details" in response.text


def test_follow_up_question_and_answer_are_persisted_and_summarized(client):
    consultation_id = create_consultation(client)
    payload = history_payload(consultation_id)
    payload.update({
        "question_key": "duration",
        "question_text": "How long have you had the fever?",
        "answer_text": "Two days, with mild body aches.",
    })

    saved = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=payload,
    )
    assert saved.status_code == 201, saved.text
    saved_payload = saved.json()["payload"]
    assert saved_payload["question_key"] == "duration"
    assert saved_payload["question_text"] == "How long have you had the fever?"
    assert saved_payload["answer_text"] == "Two days, with mild body aches."
    assert saved_payload["source"] == "patient_reported"

    summary = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json=payload,
    )
    assert summary.status_code == 200, summary.text
    assert "Two days, with mild body aches." in summary.json()["history_of_present_illness"]
