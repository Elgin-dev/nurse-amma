from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import app.main as main_module


def test_health_check_reports_database_connected(monkeypatch):
    """Return HTTP 200 when the database query succeeds."""
    connection = MagicMock()
    connection.__enter__.return_value = connection

    monkeypatch.setattr(
        main_module.engine,
        "connect",
        lambda: connection,
    )

    client = TestClient(main_module.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "connected"
    connection.execute.assert_called_once()


def test_health_check_reports_database_unavailable(monkeypatch):
    """Return HTTP 503 when the database connection fails."""

    def raise_database_error():
        raise SQLAlchemyError("Simulated database connection failure")

    monkeypatch.setattr(
        main_module.engine,
        "connect",
        raise_database_error,
    )

    client = TestClient(main_module.app)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "disconnected"

    # Internal database error details must not be exposed.
    assert "Simulated database connection failure" not in response.text
