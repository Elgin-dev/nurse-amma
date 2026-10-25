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
from app.models import Consultation, Patient, User  # noqa: F401 - register models in metadata


TEST_JWT_SECRET = "test-only-jwt-secret-that-is-long-enough-123456"
TEST_BOOTSTRAP_TOKEN = "test-only-bootstrap-token-for-tests-123456"
TEST_ADMIN_EMAIL = "admin.patient-consultation@nurseamma.test"
TEST_ADMIN_PASSWORD = "a-secure-test-password-123"


@pytest.fixture
def client(monkeypatch) -> Generator[TestClient, None, None]:
    """Provide an isolated SQLite database and authenticated API client."""
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
            # Create an administrator only in the isolated test database.
            bootstrap_response = test_client.post(
                "/api/v1/auth/bootstrap",
                headers={"X-Bootstrap-Token": TEST_BOOTSTRAP_TOKEN},
                json={
                    "email": TEST_ADMIN_EMAIL,
                    "password": TEST_ADMIN_PASSWORD,
                },
            )
            assert bootstrap_response.status_code == 201, bootstrap_response.text

            # Obtain a real signed bearer token using the application login route.
            login_response = test_client.post(
                "/api/v1/auth/login",
                json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            )
            assert login_response.status_code == 200, login_response.text
            access_token = login_response.json()["access_token"]

            # Default Authorization header keeps each legacy CRUD test authenticated.
            test_client.headers.update(
                {"Authorization": f"Bearer {access_token}"}
            )
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
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

    assert response.status_code == 201, response.text
    patient = response.json()
    assert patient["full_name"] == "Test Patient"

    patient_id = patient["id"]
    retrieved = client.get(f"/api/v1/patients/{patient_id}")

    assert retrieved.status_code == 200, retrieved.text
    assert retrieved.json()["id"] == patient_id


def test_create_and_retrieve_consultation(client: TestClient) -> None:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Consultation Test Patient"},
    )

    assert patient_response.status_code == 201, patient_response.text
    patient_id = patient_response.json()["id"]

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_id,
            "language": "en",
        },
    )

    assert response.status_code == 201, response.text
    consultation = response.json()

    assert consultation["patient_id"] == patient_id
    assert consultation["language"] == "en"
    assert consultation["status"] == "in_progress"

    consultation_id = consultation["id"]
    retrieved = client.get(f"/api/v1/consultations/{consultation_id}")

    assert retrieved.status_code == 200, retrieved.text
    assert retrieved.json()["id"] == consultation_id


def test_consultation_requires_existing_patient(client: TestClient) -> None:
    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": str(uuid4()),
            "language": "en",
        },
    )

    assert response.status_code == 404


def test_consultation_language_rejects_single_char_after_normalization(
    client: TestClient,
) -> None:
    patient_response = client.post(
        "/api/v1/patients",
        json={"full_name": "Language Validation Patient"},
    )
    assert patient_response.status_code == 201, patient_response.text

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
    assert patient_response.status_code == 201, patient_response.text

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
    assert patient_response.status_code == 201, patient_response.text

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_response.json()["id"],
            "language": " EN ",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["language"] == "en"


def test_patient_name_cannot_be_blank(client: TestClient) -> None:
    response = client.post(
        "/api/v1/patients",
        json={"full_name": "   "},
    )

    assert response.status_code == 422
