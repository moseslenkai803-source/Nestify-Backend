from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class PlatformSettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    support_email: EmailStr | None = None
    support_phone: str | None = Field(default=None, max_length=30)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    locale: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
        pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$",
    )
    currency_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    date_format: Literal[
        "DD/MM/YYYY",
        "MM/DD/YYYY",
        "YYYY-MM-DD",
    ] | None = None
    time_format: Literal["12h", "24h"] | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("organization_name", "legal_name", "support_phone", "timezone")
    @classmethod
    def strip_string_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("support_email", mode="before")
    @classmethod
    def normalize_support_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("organization_name")
    @classmethod
    def organization_name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("Organization name must not be blank")
        return value

    @field_validator("support_phone")
    @classmethod
    def validate_support_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value:
            return None
        if not all(character.isdigit() or character in "+-() ." for character in value):
            raise ValueError("Support phone contains unsupported characters")
        if value.count("+") > 1 or ("+" in value and not value.startswith("+")):
            raise ValueError("Support phone may only have a leading plus sign")
        if len([character for character in value if character.isdigit()]) < 7:
            raise ValueError("Support phone must contain at least 7 digits")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value:
            raise ValueError("Timezone must not be blank")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("legal_name", "reason")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PlatformSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_name: str
    legal_name: str | None
    support_email: EmailStr | None
    support_phone: str | None
    timezone: str
    locale: str
    currency_code: str
    date_format: str
    time_format: str
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class PlatformSettingAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID
    setting_key: str
    previous_value: str | None
    new_value: str | None
    reason: str | None
    changed_at: datetime


class EmailOutboxCounts(BaseModel):
    pending: int = 0
    processing: int = 0
    sent: int = 0
    dead_letter: int = 0


class SafeRuntimeConfiguration(BaseModel):
    debug_mode: bool
    frontend_url_configured: bool
    cors_origin_count: int
    jwt_secret_configured: bool
    outbox_encryption_configured: bool


class PlatformSettingsStatusResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    database_status: Literal["healthy", "unavailable"]
    redis_status: Literal["healthy", "unavailable", "not_required"]
    email_configuration_status: Literal["configured", "not_configured"]
    outbox_counts: EmailOutboxCounts | None
    runtime_configuration: SafeRuntimeConfiguration
