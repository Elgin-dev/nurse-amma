
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.patient import Patient  # noqa: F401
from app.models.consultation import Consultation  # noqa: F401


@pytest.fixture
def client():
    """Provide an isolated SQLite database for API integration tests."""
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

    def override_get_db():
        db = TestingSessionLocal()
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
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def create_consultation(client: TestClient) -> str:
    """Create a patient and consultation through the public API."""
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


def test_next_question_for_existing_consultation(client):
    consultation_id = create_consultation(client)

    response = client.post(
        f"/api/v1/consultations/{consultation_id}/next-question",
        params={"chief_complaint": "fever"},
    )

    assert response.status_code == 200
    assert response.json()["question_key"] == "duration"
    assert response.json()["is_complete"] is False


def test_next_question_returns_404_for_missing_consultation(client):
    missing_id = str(uuid4())

    response = client.post(
        f"/api/v1/consultations/{missing_id}/next-question",
        params={"chief_complaint": "fever"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Consultation not found"


def test_summary_rejects_mismatched_consultation_ids(client):
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


def test_summary_for_existing_consultation(client):
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
