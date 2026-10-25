from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Consultation, Patient


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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

    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_create_and_retrieve_patient(client: TestClient) -> None:
    response = client.post(
        "/api/v1/patients",
        json={
            "full_name": "Test Patient",
            "date_of_birth": "2000-01-15",
        },
    )

    assert response.status_code == 201
    patient = response.json()
    assert patient["full_name"] == "Test Patient"

    patient_id = patient["id"]
    retrieved = client.get(f"/api/v1/patients/{patient_id}")

    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == patient_id


def test_create_and_retrieve_consultation(
    client: TestClient,
) -> None:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Consultation Test Patient"},
    )

    assert patient_response.status_code == 201
    patient_id = patient_response.json()["id"]

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_id,
            "language": "en",
        },
    )

    assert response.status_code == 201
    consultation = response.json()

    assert consultation["patient_id"] == patient_id
    assert consultation["language"] == "en"
    assert consultation["status"] == "in_progress"

    consultation_id = consultation["id"]
    retrieved = client.get(
        f"/api/v1/consultations/{consultation_id}"
    )

    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == consultation_id


def test_consultation_requires_existing_patient(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": str(uuid4()),
            "language": "en",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found."


def test_consultation_language_rejects_single_char_after_normalization(
    client: TestClient,
) -> None:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Language Validation Patient"},
    )
    assert patient_response.status_code == 201

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_response.json()["id"],
            "language": " a ",
        },
    )

    assert response.status_code == 422


def test_consultation_language_rejects_whitespace_only(
    client: TestClient,
) -> None:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Language Validation Patient"},
    )
    assert patient_response.status_code == 201

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_response.json()["id"],
            "language": "   ",
        },
    )

    assert response.status_code == 422


def test_consultation_language_normalizes_valid_value(
    client: TestClient,
) -> None:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Language Validation Patient"},
    )
    assert patient_response.status_code == 201

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_response.json()["id"],
            "language": " EN ",
        },
    )

    assert response.status_code == 201
    assert response.json()["language"] == "en"


def test_patient_name_cannot_be_blank(client: TestClient) -> None:
    response = client.post(
        "/api/v1/patients",
        json={"full_name": "   "},
    )

    assert response.status_code == 422