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


def test_readiness_checks_redis_in_staging(monkeypatch):
    from unittest.mock import MagicMock

    import app.main as main_module

    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(main_module.engine, "connect", lambda: connection)
    monkeypatch.setattr(main_module.settings, "environment", "staging")

    rate_limit_service = MagicMock()
    rate_limit_service.check_store_health.return_value = True
    monkeypatch.setattr(
        main_module,
        "get_rate_limit_service",
        lambda: rate_limit_service,
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
        "redis": "ok",
    }
    rate_limit_service.check_store_health.assert_called_once()


def test_readiness_returns_503_when_redis_is_unavailable(monkeypatch):
    from unittest.mock import MagicMock

    import app.main as main_module

    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(main_module.engine, "connect", lambda: connection)
    monkeypatch.setattr(main_module.settings, "environment", "production")

    rate_limit_service = MagicMock()
    rate_limit_service.check_store_health.return_value = False
    monkeypatch.setattr(
        main_module,
        "get_rate_limit_service",
        lambda: rate_limit_service,
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ok",
        "redis": "unavailable",
    }
    rate_limit_service.check_store_health.assert_called_once()


def test_readiness_does_not_require_redis_in_development(monkeypatch):
    from unittest.mock import MagicMock

    import app.main as main_module

    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(main_module.engine, "connect", lambda: connection)
    monkeypatch.setattr(main_module.settings, "environment", "development")

    get_rate_limit_service = MagicMock()
    monkeypatch.setattr(
        main_module,
        "get_rate_limit_service",
        get_rate_limit_service,
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
    }
    get_rate_limit_service.assert_not_called()
