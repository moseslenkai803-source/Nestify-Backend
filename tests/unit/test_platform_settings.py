from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.platform_settings import PlatformSettingUpdate
from app.services.platform_settings_service import PlatformSettingsService


def make_setting():
    return SimpleNamespace(
        id=1,
        organization_name="Nestify",
        legal_name=None,
        support_email=None,
        support_phone=None,
        timezone="Africa/Nairobi",
        locale="en-KE",
        currency_code="KES",
        date_format="DD/MM/YYYY",
        time_format="24h",
        updated_by=None,
        updated_at=None,
    )


def make_service(setting):
    db = MagicMock()
    db.scalar.return_value = setting
    return PlatformSettingsService(db), db


def test_update_creates_one_audit_entry_per_changed_field():
    setting = make_setting()
    service, db = make_service(setting)
    actor_id = uuid4()

    result = service.update_settings(
        PlatformSettingUpdate(
            organization_name="  Nestify Technologies  ",
            support_email=" support@nestify.example ",
            reason="Company details updated",
        ),
        actor_id,
    )

    assert result is setting
    assert setting.organization_name == "Nestify Technologies"
    assert setting.support_email == "support@nestify.example"
    assert setting.updated_by == actor_id
    assert setting.updated_at is not None

    db.add_all.assert_called_once()
    audit_entries = db.add_all.call_args.args[0]
    assert {entry.setting_key for entry in audit_entries} == {
        "organization_name",
        "support_email",
    }
    assert all(entry.actor_user_id == actor_id for entry in audit_entries)
    assert all(entry.reason == "Company details updated" for entry in audit_entries)
    db.flush.assert_called_once()


def test_unchanged_values_do_not_create_audit_entries_or_change_metadata():
    setting = make_setting()
    original_updated_at = object()
    setting.updated_at = original_updated_at
    service, db = make_service(setting)

    service.update_settings(
        PlatformSettingUpdate(organization_name="Nestify"),
        uuid4(),
    )

    db.add_all.assert_not_called()
    assert setting.updated_by is None
    assert setting.updated_at is original_updated_at
    db.flush.assert_called_once()


def test_invalid_null_field_does_not_partially_mutate_settings():
    setting = make_setting()
    service, db = make_service(setting)

    with pytest.raises(ValueError, match="timezone cannot be null"):
        service.update_settings(
            PlatformSettingUpdate(
                organization_name="Changed Name",
                timezone=None,
            ),
            uuid4(),
        )

    assert setting.organization_name == "Nestify"
    assert setting.timezone == "Africa/Nairobi"
    db.add_all.assert_not_called()
    db.flush.assert_not_called()


def test_schema_strips_support_email_and_converts_blank_to_none():
    payload = PlatformSettingUpdate(support_email="  help@nestify.example  ")
    assert str(payload.support_email) == "help@nestify.example"

    blank_payload = PlatformSettingUpdate(support_email="   ")
    assert blank_payload.support_email is None


def test_schema_rejects_invalid_timezone():
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        PlatformSettingUpdate(timezone="Not/A_Timezone")


def test_schema_rejects_misplaced_phone_plus_sign():
    with pytest.raises(ValidationError, match="leading plus sign"):
        PlatformSettingUpdate(support_phone="254+712345678")
