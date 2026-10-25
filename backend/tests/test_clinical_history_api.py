from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import ClinicalHistorySubmission


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

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db

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
        json={
            "patient_id": patient_id,
            "language": "en",
        },
    )
    assert consultation_response.status_code == 201, consultation_response.text

    return consultation_response.json()["id"]


def history_payload(consultation_id: str) -> dict:
    """Return a synthetic structured history submission."""
    return {
        "consultation_id": consultation_id,
        "chief_complaint": "fever",
        "symptom_details": {
            "duration": {
                "value": 4,
                "unit": "days",
            },
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


def test_next_question_returns_404_for_missing_consultation(
    client: TestClient,
):
    missing_id = str(uuid4())

    response = client.post(
        f"/api/v1/consultations/{missing_id}/next-question",
        params={"chief_complaint": "fever"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"


def test_summary_rejects_mismatched_consultation_ids(
    client: TestClient,
):
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
    assert response.json()["detail"] == (
        "consultation_id in request body must match the URL"
    )


def test_summary_for_existing_consultation(client: TestClient):
    consultation_id = create_consultation(client)

    response = client.post(
        f"/api/v1/consultations/{consultation_id}/summary",
        json={
            "consultation_id": consultation_id,
            "chief_complaint": "fever",
            "symptom_details": {
                "duration": {
                    "value": 4,
                    "unit": "days",
                }
            },
            "associated_symptoms": ["Altered Sensorium"],
            "current_medications": ["Medication A"],
        },
    )

    assert response.status_code == 200
    result = response.json()

    assert result["consultation_id"] == consultation_id
    assert result["summary_id"].startswith("SUM-")
    assert result["review_status"] == "pending_doctor_approval"
    assert len(result["red_flags"]) == 1
    assert result["red_flags"][0]["flag_id"] == "RF-001"
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


def test_saved_history_exists_in_database(
    client: TestClient,
    testing_session_local,
):
    consultation_id = create_consultation(client)

    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=history_payload(consultation_id),
    )

    assert response.status_code == 201, response.text
    saved_id = UUID(response.json()["id"])

    # Use a separate session to verify the committed record is queryable.
    with testing_session_local() as db:
        saved = db.get(ClinicalHistorySubmission, saved_id)

        assert saved is not None
        assert saved.consultation_id == UUID(consultation_id)
        assert saved.version == 1
        assert saved.payload["chief_complaint"] == "fever"


def test_history_submission_versions_increase(
    client: TestClient,
    testing_session_local,
):
    consultation_id = create_consultation(client)
    url = f"/api/v1/consultations/{consultation_id}/responses"
    payload = history_payload(consultation_id)

    first = client.post(url, json=payload)
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
            select(func.count())
            .select_from(ClinicalHistorySubmission)
            .where(
                ClinicalHistorySubmission.consultation_id
                == UUID(consultation_id)
            )
        )

        assert count == 2


def test_history_rejects_mismatched_consultation_ids(
    client: TestClient,
):
    consultation_id = create_consultation(client)
    payload = history_payload(str(uuid4()))

    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "consultation_id in request body must match the URL"
    )


def test_history_rejects_invalid_body_consultation_id(
    client: TestClient,
):
    consultation_id = create_consultation(client)
    payload = history_payload(consultation_id)
    payload["consultation_id"] = "not-a-valid-uuid"

    response = client.post(
        f"/api/v1/consultations/{consultation_id}/responses",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Invalid consultation_id in request body"
    )


def test_history_returns_404_for_missing_consultation(
    client: TestClient,
):
    missing_id = str(uuid4())

    response = client.post(
        f"/api/v1/consultations/{missing_id}/responses",
        json=history_payload(missing_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"