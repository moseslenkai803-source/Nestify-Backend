from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PropertyInstallationCreate(BaseModel):
    plate_id: UUID
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


class PropertyInstallationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    plate_id: UUID
    assignment_id: UUID | None
    installer_id: UUID
    latitude: float
    longitude: float
    accuracy_meters: float | None
    captured_at: datetime
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
