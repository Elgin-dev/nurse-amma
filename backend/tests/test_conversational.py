from collections.abc import Generator
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.main import app
from app.routers import clinical_history as clinical_history_router
from app.schemas.clinical_history import ExtractedClinicalContext
from app.services.conversational_engine import ConversationalEngine


class FakeHTTPResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": json.dumps(self._content)}}


def _ollama_http_response(next_question, extracted_data):
    return FakeHTTPResponse(
        {
            "next_question": next_question,
            "extracted_data": extracted_data,
        }
    )


@pytest.fixture
def dynamic_client(monkeypatch) -> Generator[TestClient, None, None]:
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: object()

    def allow_consultation_access(_db, _consultation_id, _user):
        return None

    monkeypatch.setattr(
        clinical_history_router,
        "require_consultation_access",
        allow_consultation_access,
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


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
    assert seen_histories[0]["model"] == "gemma3:1b"
    assert seen_histories[0]["messages"][-1] == {
        "role": "user",
        "content": "I have a fever",
    }
    assert seen_histories[0]["format"] == "json"

    second_response = dynamic_client.post(
        f"/api/v1/consultations/{consultation_id}/dynamic-intake",
        json={
            "consultation_id": consultation_id,
            "chat_history": [
                {"role": "user", "content": "I have a fever"},
                {
                    "role": "assistant",
                    "content": "How long have you had the fever?",
                },
                {"role": "user", "content": "For three days"},
            ],
        },
    )

    assert second_response.status_code == 200
    assert len(seen_histories) == 2
    assert seen_histories[1]["messages"][-1]["content"] == "For three days"


@pytest.mark.parametrize(
    "trigger",
    ("chest pain", "stiff neck", "seizure", "unconscious"),
)
def test_dynamic_intake_safety_override_bypasses_ollama(
    dynamic_client: TestClient,
    monkeypatch,
    trigger: str,
):
    consultation_id = str(uuid4())

    def unexpected_ollama_call(*args, **kwargs):
        raise AssertionError("Emergency messages must not be sent to Ollama")

    monkeypatch.setattr(
        "app.services.conversational_engine.httpx.post",
        unexpected_ollama_call,
    )
    response = dynamic_client.post(
        f"/api/v1/consultations/{consultation_id}/dynamic-intake",
        json={
            "consultation_id": consultation_id,
            "chat_history": [{"role": "user", "content": f"I have {trigger}"}],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "EMERGENCY_ESCALATION"
    assert result["red_flag_alert"]["severity"] == "high"
    assert trigger in result["red_flag_alert"]["trigger"]


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
    result = response.json()
    assert result["status"] == "COMPLETED"
    assert result["next_question"] == ""
    assert result["doctor_summary"]["consultation_id"] == consultation_id
    assert result["doctor_summary"]["fever_mechanism"] == (
        "evening spikes with chills"
    )
    assert "not a diagnosis" in result["doctor_summary"]["clinical_review_note"]


def test_offline_engine_extracts_fever_details_when_ollama_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Ollama is unavailable")

    monkeypatch.setattr("app.services.conversational_engine.httpx.post", unavailable)
    result = ConversationalEngine.process_turn_local(
        [
            {"role": "user", "content": "I have a fever"},
            {
                "role": "assistant",
                "content": "How long have you had the fever?",
            },
            {"role": "user", "content": "For three days"},
            {
                "role": "assistant",
                "content": "How severe does it feel?",
            },
            {"role": "user", "content": "Moderate, with intermittent spikes"},
            {
                "role": "assistant",
                "content": "Any other symptoms?",
            },
            {"role": "user", "content": "No other symptoms"},
        ],
    )

    extracted = result["extracted_data"]
    assert extracted.chief_complaint == "fever"
    assert extracted.duration == "3 days"
    assert extracted.severity == "moderate"
    assert extracted.fever_mechanism == "intermittent"
    assert extracted.associated_symptoms == ["None reported"]
    assert extracted.is_complete is True
    assert result["next_question"] == ""


def test_ollama_completion_is_rejected_without_fever_pattern(monkeypatch):
    monkeypatch.setattr(
        "app.services.conversational_engine.httpx.post",
        lambda *args, **kwargs: _ollama_http_response(
            "When does the fever spike?",
            {
                "chief_complaint": "fever",
                "duration": "3 days",
                "severity": "moderate",
                "fever_mechanism": "chills and sweating",
                "associated_symptoms": ["chills"],
                "is_complete": True,
            },
        ),
    )

    result = ConversationalEngine.process_turn_local(
        [{"role": "user", "content": "I have a fever"}],
    )

    assert result["extracted_data"].is_complete is False
    assert result["next_question"] == "When does the fever spike?"


def test_partial_ollama_response_uses_offline_extraction_and_model_question(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.conversational_engine.httpx.post",
        lambda *args, **kwargs: FakeHTTPResponse(
            {"next_question": "When did the fever start?"}
        ),
    )

    result = ConversationalEngine.process_turn_local(
        [{"role": "user", "content": "I have a fever"}],
    )

    assert result["next_question"] == "When did the fever start?"
    assert result["extracted_data"].chief_complaint == "fever"
    assert result["extracted_data"].is_complete is False
