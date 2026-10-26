from collections.abc import Generator
from typing import Tuple
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.patient_consent import PatientConsent

TEST_JWT_SECRET = "test-only-jwt-secret-for-consent-tests-2026"
TEST_BOOTSTRAP_TOKEN = "test-only-bootstrap-token-consent-tests-2026"
TEST_ADMIN_EMAIL = "admin.consent-tests@nurseamma.test"
TEST_ADMIN_PASSWORD = "a-secure-consent-test-password-123"


@pytest.fixture
def client_and_db(monkeypatch) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    """Yields both the TestClient and the sessionmaker for DB assertions."""
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
            
            yield test_client, testing_session_local
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_create_patient_without_consent_fails(client_and_db):
    """Verify the backend rejects patient creation if consent_confirmed is missing."""
    client, _ = client_and_db
    res = client.post("/api/v1/patients", json={"full_name": "No Consent Patient"})
    assert res.status_code == 400
    assert "consent must be confirmed" in res.json()["detail"].lower()


def test_create_patient_with_consent_succeeds(client_and_db):
    """Verify patient creation succeeds and creates exactly ONE consent row."""
    client, session_maker = client_and_db
    res = client.post(
        "/api/v1/patients", 
        json={"full_name": "Consent Test", "consent_confirmed": True}
    )
    assert res.status_code == 201
    patient_id_str = res.json()["id"]
    assert res.json()["full_name"] == "Consent Test"

    # Cast string back to UUID object for the SQLAlchemy query
    patient_id = UUID(patient_id_str)

    # Assert exactly one consent row was created for this patient in the DB
    with session_maker() as db:
        count = db.scalar(
            select(func.count()).select_from(PatientConsent).where(PatientConsent.patient_id == patient_id)
        )
        assert count == 1, f"Expected exactly 1 consent record, found {count}"