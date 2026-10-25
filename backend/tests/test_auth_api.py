from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User


@pytest.fixture
def auth_client(monkeypatch) -> Generator[TestClient, None, None]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr(settings, "jwt_secret_key", "test-only-jwt-secret-that-is-long-enough-123456")
    monkeypatch.setattr(settings, "bootstrap_admin_token", "test-only-bootstrap-token-for-tests-123456")
    monkeypatch.setattr(settings, "access_token_expire_minutes", 60)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def bootstrap_admin(client: TestClient, email: str = "admin@nurseamma.test") -> dict:
    response = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": "test-only-bootstrap-token-for-tests-123456"},
        json={"email": email, "password": "a-secure-test-password-123"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str = "admin@nurseamma.test") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "a-secure-test-password-123"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] > 0
    return payload["access_token"]


def test_protected_me_and_patient_routes_require_bearer_token(auth_client: TestClient):
    response = auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"

    response = auth_client.get("/api/v1/patients/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 401


def test_bootstrap_rejects_wrong_token(auth_client: TestClient):
    response = auth_client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": "wrong-token"},
        json={"email": "admin@nurseamma.test", "password": "a-secure-test-password-123"},
    )
    assert response.status_code == 403


def test_bootstrap_login_and_me(auth_client: TestClient):
    created = bootstrap_admin(auth_client)
    assert created["role"] == "admin"
    assert "password_hash" not in created

    token = login(auth_client)
    response = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "admin@nurseamma.test"
    assert response.json()["role"] == "admin"


def test_bootstrap_is_only_available_once(auth_client: TestClient):
    bootstrap_admin(auth_client)
    response = auth_client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": "test-only-bootstrap-token-for-tests-123456"},
        json={"email": "second-admin@nurseamma.test", "password": "another-secure-password-123"},
    )
    assert response.status_code == 409


def test_admin_can_create_clinician_account(auth_client: TestClient):
    bootstrap_admin(auth_client)
    token = login(auth_client)
    response = auth_client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "doctor@nurseamma.test", "password": "another-secure-password-123"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "clinician"
    assert response.json()["email"] == "doctor@nurseamma.test"

    # The API response intentionally never exposes the stored password hash.
    assert "password_hash" not in response.json()
