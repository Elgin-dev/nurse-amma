import json
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.schemas.clinical_history import ExtractedClinicalContext


class FakeHTTPResponse:
    def __init__(self, content: dict):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": json.dumps(self._content)}}


def _ollama_http_response(next_q: str, extracted: dict) -> FakeHTTPResponse:
    return FakeHTTPResponse({"next_question": next_q, "extracted_data": extracted})


@pytest.fixture
def dynamic_client(monkeypatch) -> Generator[TestClient, None, None]:
    # Mock the database to prevent saving to Postgres during unit tests
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.return_value = None  # Simulate no existing history

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    
    # We don't need real auth for these unit tests
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid4(), role="admin")
    
    # Mock consultation access
    monkeypatch.setattr(
        "app.routers.clinical_history.require_consultation_access", 
        lambda *args, **kwargs: None
    )

    with TestClient(app) as client:
        yield client
        
    app.dependency_overrides.clear()


def test_dynamic_intake_supports_a_multi_turn_flow(
    dynamic_client: TestClient,
    monkeypatch,
):
    consultation_id = str(uuid4())
    seen_histories = []
    def mock_post(url, *, json, timeout):
        seen_histories.append(json)
        return _ollama_http_response(
            "How long have you had the fever?",
            {"chief_complaint": "fever", "is_complete": False},
        )
    monkeypatch.setattr("app.services.conversational_engine.httpx.post", mock_post)
    response = dynamic_client.post(
        f"/api/v1/consultations/{consultation_id}/dynamic-intake",
        json={
            "consultation_id": consultation_id,
            "chat_history": [{"role": "user", "content": "I have a fever"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["next_question"] == "How long have you had the fever?"
    # Use the dynamic settings so it matches whatever is in your .env
    assert seen_histories[0]["model"] == settings.ollama_model


def test_completed_intake_returns_doctor_review_summary(
    dynamic_client: TestClient,
    monkeypatch,
):
    consultation_id = str(uuid4())
    extracted_data = ExtractedClinicalContext(
        chief_complaint="fever",
        duration="3 days",
        severity="moderate",
        fever_mechanism="evening spikes with chills",
        associated_symptoms=["chills", "headache"],
        aggravating_relieving_factors="worse at night",
        is_complete=True,
    )
    monkeypatch.setattr(
        "app.services.conversational_engine.httpx.post",
        lambda *args, **kwargs: _ollama_http_response("", extracted_data.model_dump()),
    )
    response = dynamic_client.post(
        f"/api/v1/consultations/{consultation_id}/dynamic-intake",
        json={
            "consultation_id": consultation_id,
            "chat_history": [{"role": "user", "content": "I have a fever"}],
        },
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["next_question"] == ""
    assert response.json()["doctor_summary"]["chief_complaint"] == "fever"