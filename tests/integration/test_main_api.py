from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_cors_allows_control_portal_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_unapproved_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 400


def test_readiness_returns_ready_when_database_is_available(monkeypatch):
    from unittest.mock import MagicMock

    import app.main as main_module

    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(
        main_module.engine,
        "connect",
        lambda: connection,
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
    }
    connection.execute.assert_called_once()


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    import app.main as main_module

    def fail_to_connect():
        raise SQLAlchemyError("sensitive database connection details")

    monkeypatch.setattr(
        main_module.engine,
        "connect",
        fail_to_connect,
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
    assert "sensitive database connection details" not in response.text
