from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Patient, User

TEST_JWT_SECRET = "test-only-jwt-secret-for-consent-tests-2026"
TEST_BOOTSTRAP_TOKEN = "test-only-bootstrap-token-consent-tests-2026"
TEST_ADMIN_EMAIL = "admin.consent-tests@nurseamma.test"
TEST_ADMIN_PASSWORD = "a-secure-consent-test-password-123"

@pytest.fixture
def client(monkeypatch) -> Generator[TestClient, None, None]:
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

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
            test_client.post(
                "/api/v1/auth/bootstrap",
                headers={"X-Bootstrap-Token": TEST_BOOTSTRAP_TOKEN},
                json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            )
            login_response = test_client.post(
                "/api/v1/auth/login",
                json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            )
            token = login_response.json()["access_token"]
            test_client.headers.update({"Authorization": f"Bearer {token}"})
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_record_consent_for_own_patient(client: TestClient):
    # 1. Create patient
    patient_res = client.post("/api/v1/patients", json={"full_name": "Consent Test"})
    assert patient_res.status_code == 201
    patient_id = patient_res.json()["id"]

    # 2. Record consent
    consent_res = client.post(
        f"/api/v1/patients/{patient_id}/consent",
        json={"consent_version": "1.0"}
    )
    assert consent_res.status_code == 201, consent_res.text
    data = consent_res.json()
    assert data["patient_id"] == patient_id
    assert data["consent_version"] == "1.0"
    assert "consented_at" in data


def test_record_consent_for_missing_patient(client: TestClient):
    missing_id = str(uuid4())
    res = client.post(
        f"/api/v1/patients/{missing_id}/consent",
        json={"consent_version": "1.0"}
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Patient not found"