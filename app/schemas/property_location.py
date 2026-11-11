from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PropertyLocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    source: str = Field(min_length=1, max_length=50)
    capture_method: str = Field(min_length=1, max_length=100)
    accuracy_meters: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    captured_at: datetime

    @field_validator("source", "capture_method")
    @classmethod
    def reject_blank_provenance(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @field_validator("captured_at")
    @classmethod
    def captured_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value


class PropertyLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    latitude: float
    longitude: float
    source: str
    capture_method: str
    accuracy_meters: float | None
    captured_at: datetime
    status: str


class PropertyLocationDecisionCreate(BaseModel):
    verification_method: str = Field(min_length=1, max_length=100)
    notes: str | None = None


class PropertyLocationVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    verified_by: UUID
    decision: Literal["approved", "rejected"]
    verification_method: str
    verified_at: datetime
    notes: str | None
    created_at: datetime


class PropertyLocationHistoryResponse(BaseModel):
    id: UUID
    property_id: UUID
    version_number: int
    submitted_by_id: UUID | None
    submitted_at: datetime | None
    latitude: float
    longitude: float
    source: str
    capture_method: str
    accuracy_meters: float | None
    captured_at: datetime
    status: str
    is_current: bool
    history_state: Literal[
        "legacy",
        "pending",
        "current",
        "superseded",
        "rejected",
    ]
    verification: PropertyLocationVerificationResponse | None
