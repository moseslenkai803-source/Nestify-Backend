"""Database-backed tests for platform settings and audit history."""

from uuid import uuid4

from sqlalchemy import select

from app.models.platform_setting import PlatformSetting
from app.models.platform_setting_audit_log import PlatformSettingAuditLog
from app.models.user import User
from app.schemas.platform_settings import PlatformSettingUpdate
from app.services.platform_settings_service import PlatformSettingsService


def create_admin(db_session):
    admin = User(
        id=uuid4(),
        email=f"settings-admin-{uuid4()}@example.invalid",
        password_hash="not-a-real-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    return admin


def test_get_settings_returns_seeded_singleton(db_session):
    service = PlatformSettingsService(db_session)

    setting = service.get_settings()

    assert setting.id == 1
    assert setting.organization_name == "Nestify"
    assert setting.timezone == "Africa/Nairobi"
    assert setting.locale == "en-KE"
    assert setting.currency_code == "KES"
    assert setting.date_format == "DD/MM/YYYY"
    assert setting.time_format == "24h"


def test_update_persists_settings_and_one_audit_row_per_changed_field(
    db_session,
):
    admin = create_admin(db_session)
    service = PlatformSettingsService(db_session)

    updated = service.update_settings(
        PlatformSettingUpdate(
            organization_name="Nestify Technologies",
            support_email="support@nestify.example",
            timezone="Africa/Nairobi",
            reason="Initial organization configuration",
        ),
        admin.id,
    )

    db_session.flush()
    db_session.expire_all()

    persisted = db_session.scalar(
        select(PlatformSetting).where(PlatformSetting.id == 1)
    )

    assert persisted is not None
    assert persisted.organization_name == "Nestify Technologies"
    assert persisted.support_email == "support@nestify.example"
    assert persisted.updated_by == admin.id

    audit_rows = list(
        db_session.scalars(
            select(PlatformSettingAuditLog).where(
                PlatformSettingAuditLog.actor_user_id == admin.id
            )
        ).all()
    )

    assert len(audit_rows) == 2

    audit_by_key = {entry.setting_key: entry for entry in audit_rows}

    assert set(audit_by_key) == {"organization_name", "support_email"}

    assert audit_by_key["organization_name"].previous_value == "Nestify"
    assert (
        audit_by_key["organization_name"].new_value
        == "Nestify Technologies"
    )

    assert audit_by_key["support_email"].previous_value is None
    assert (
        audit_by_key["support_email"].new_value
        == "support@nestify.example"
    )

    assert all(
        entry.reason == "Initial organization configuration"
        for entry in audit_rows
    )
    assert updated.updated_by == admin.id


def test_unchanged_update_does_not_create_audit_history(db_session):
    admin = create_admin(db_session)
    service = PlatformSettingsService(db_session)

    original = service.get_settings()
    original_updated_at = original.updated_at

    service.update_settings(
        PlatformSettingUpdate(
            organization_name="Nestify",
            currency_code="KES",
        ),
        admin.id,
    )

    audit_rows = list(
        db_session.scalars(
            select(PlatformSettingAuditLog).where(
                PlatformSettingAuditLog.actor_user_id == admin.id
            )
        ).all()
    )

    assert audit_rows == []

    db_session.refresh(original)
    assert original.updated_by is None
    assert original.updated_at == original_updated_at


def test_invalid_null_update_does_not_persist_partial_changes(db_session):
    admin = create_admin(db_session)
    service = PlatformSettingsService(db_session)

    try:
        service.update_settings(
            PlatformSettingUpdate(
                organization_name="Must Not Persist",
                timezone=None,
            ),
            admin.id,
        )
    except ValueError as exc:
        assert str(exc) == "timezone cannot be null"
    else:
        raise AssertionError("Expected null timezone update to be rejected")

    db_session.expire_all()
    persisted = service.get_settings()

    assert persisted.organization_name == "Nestify"
    assert persisted.timezone == "Africa/Nairobi"

    audit_rows = list(
        db_session.scalars(
            select(PlatformSettingAuditLog).where(
                PlatformSettingAuditLog.actor_user_id == admin.id
            )
        ).all()
    )
    assert audit_rows == []


def test_audit_listing_applies_limit_and_offset(db_session):
    first_admin = create_admin(db_session)
    second_admin = create_admin(db_session)
    service = PlatformSettingsService(db_session)

    service.update_settings(
        PlatformSettingUpdate(organization_name="Nestify One"),
        first_admin.id,
    )
    service.update_settings(
        PlatformSettingUpdate(organization_name="Nestify Two"),
        second_admin.id,
    )

    all_rows = service.list_audit_logs(limit=10, offset=0)
    page = service.list_audit_logs(limit=1, offset=1)

    assert len(all_rows) == 2
    assert len(page) == 1
    assert page[0].id == all_rows[1].id
