"""Integration tests for the admin-only platform settings API."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.platform_setting_audit_log import PlatformSettingAuditLog
from app.models.user import User
from app.services.email_service import EmailService


def create_user(db_session, *, role="admin", is_active=True):
    user = User(
        id=uuid4(),
        email=f"settings-api-{uuid4()}@example.invalid",
        password_hash="not-a-real-password-hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def auth_headers(user):
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_retrieve_seeded_platform_settings(db_session):
    admin = create_user(db_session)
    response = TestClient(app).get(
        "/api/v1/settings",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["id"] == 1
    assert data["organization_name"] == "Nestify"
    assert data["timezone"] == "Africa/Nairobi"
    assert data["locale"] == "en-KE"
    assert data["currency_code"] == "KES"
    assert data["date_format"] == "DD/MM/YYYY"
    assert data["time_format"] == "24h"


def test_settings_endpoints_reject_unauthenticated_requests():
    client = TestClient(app)

    for method, path in (
        ("get", "/api/v1/settings"),
        ("patch", "/api/v1/settings"),
        ("get", "/api/v1/settings/audit-logs"),
        ("get", "/api/v1/settings/status"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, (
            f"{method.upper()} {path}: {response.text}"
        )


def test_non_admin_cannot_access_platform_settings(db_session):
    employee = create_user(db_session, role="employee")
    headers = auth_headers(employee)
    client = TestClient(app)

    for method, path in (
        ("get", "/api/v1/settings"),
        ("patch", "/api/v1/settings"),
        ("get", "/api/v1/settings/audit-logs"),
        ("get", "/api/v1/settings/status"),
    ):
        if method == "patch":
            response = client.patch(
                path,
                headers=headers,
                json={"organization_name": "Unauthorized Change"},
            )
        else:
            response = getattr(client, method)(path, headers=headers)
        assert response.status_code == 403, (
            f"{method.upper()} {path}: {response.text}"
        )


def test_admin_can_update_settings_and_retrieve_audit_history(db_session):
    admin = create_user(db_session)
    headers = auth_headers(admin)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/settings",
        headers=headers,
        json={
            "organization_name": "Nestify Technologies",
            "support_email": "support@nestify.example",
            "reason": "Configure organization profile",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["organization_name"] == "Nestify Technologies"
    assert response.json()["support_email"] == "support@nestify.example"
    assert response.json()["updated_by"] == str(admin.id)

    audit_response = client.get(
        "/api/v1/settings/audit-logs",
        headers=headers,
    )

    assert audit_response.status_code == 200, audit_response.text
    audit_rows = audit_response.json()

    assert len(audit_rows) == 2
    assert {row["setting_key"] for row in audit_rows} == {
        "organization_name",
        "support_email",
    }
    assert all(row["actor_user_id"] == str(admin.id) for row in audit_rows)
    assert all(
        row["reason"] == "Configure organization profile"
        for row in audit_rows
    )

    persisted_audit_count = (
        db_session.query(PlatformSettingAuditLog)
        .filter(PlatformSettingAuditLog.actor_user_id == admin.id)
        .count()
    )
    assert persisted_audit_count == 2


def test_invalid_settings_update_is_rejected_without_partial_changes(
    db_session,
):
    admin = create_user(db_session)

    response = TestClient(app).patch(
        "/api/v1/settings",
        headers=auth_headers(admin),
        json={
            "organization_name": "Must Not Persist",
            "timezone": None,
        },
    )

    assert response.status_code == 422, response.text

    get_response = TestClient(app).get(
        "/api/v1/settings",
        headers=auth_headers(admin),
    )

    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["organization_name"] == "Nestify"
    assert get_response.json()["timezone"] == "Africa/Nairobi"

    assert (
        db_session.query(PlatformSettingAuditLog)
        .filter(PlatformSettingAuditLog.actor_user_id == admin.id)
        .count()
        == 0
    )


def test_admin_can_retrieve_safe_operational_status(
    db_session,
    monkeypatch,
):
    admin = create_user(db_session)

    from app.api.v1 import settings as settings_api

    monkeypatch.setattr(settings_api.settings, "environment", "development")
    monkeypatch.setattr(
        EmailService,
        "is_configured",
        staticmethod(lambda: True),
    )

    response = TestClient(app).get(
        "/api/v1/settings/status",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["environment"] == "development"
    assert data["database_status"] == "healthy"
    assert data["redis_status"] == "not_required"
    assert data["email_configuration_status"] == "configured"
    assert data["outbox_counts"] == {
        "pending": 0,
        "processing": 0,
        "sent": 0,
        "dead_letter": 0,
    }

    assert "jwt_secret_key" not in str(data).lower()
    assert "outbox_encryption_keys" not in str(data).lower()
    assert "password" not in str(data).lower()


def test_audit_log_pagination_rejects_out_of_range_limits(db_session):
    admin = create_user(db_session)

    response = TestClient(app).get(
        "/api/v1/settings/audit-logs?limit=101",
        headers=auth_headers(admin),
    )

    assert response.status_code == 422, response.text
