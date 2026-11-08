from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class InstallationAssignmentCreate(BaseModel):
    property_id: UUID
    plate_id: UUID
    contractor_id: UUID
    contractor_member_id: UUID
    due_at: datetime | None = None


class InstallationAssignmentMemberResponse(BaseModel):
    id: UUID
    contractor_id: UUID
    user_id: UUID
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InstallationAssignmentPlateResponse(BaseModel):
    id: UUID
    plate_code: str
    property_id: UUID


class InstallationAssignmentCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class InstallationAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    property_name: str
    plate_id: UUID
    plate_code: str
    contractor_id: UUID
    contractor_name: str
    contractor_member_id: UUID
    installer_email: str
    assigned_by: UUID
    assigned_by_email: str
    assigned_at: datetime
    due_at: datetime | None
    status: str
    cancelled_by: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime


class InstallationAssignmentSubmit(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_meters: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    captured_at: datetime
    notes: str | None = None

    @field_validator("captured_at")
    @classmethod
    def captured_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value
