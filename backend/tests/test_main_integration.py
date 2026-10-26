from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.clinical_history import PatientResponseInput


def test_test_ui_is_served():
    response = TestClient(app).get("/test-ui")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI Clinical History Sandbox" in response.text


def test_cors_allows_configured_frontend_origin():
    response = TestClient(app).options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_clinical_history_routes_are_registered():
    registered_routes = app.openapi()["paths"]

    assert "post" in registered_routes[
        "/api/v1/consultations/{consultation_id}/next-question"
    ]
    assert "post" in registered_routes["/api/v1/consultations/{consultation_id}/summary"]
    assert "post" in registered_routes[
        "/api/v1/consultations/{consultation_id}/process-speech"
    ]


def test_null_optional_history_fields_use_empty_defaults():
    payload = PatientResponseInput.model_validate(
        {
            "consultation_id": str(uuid4()),
            "chief_complaint": "fever",
            "symptom_details": None,
            "associated_symptoms": None,
            "past_medical_history": None,
            "current_medications": None,
            "allergies": None,
        }
    )

    assert payload.symptom_details.duration is None
    assert payload.associated_symptoms == []
    assert payload.past_medical_history == []
    assert payload.current_medications == []
    assert payload.allergies == []
