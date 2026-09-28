from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InstallationAssignmentCreate(BaseModel):
    property_id: UUID
    plate_id: UUID
    contractor_id: UUID
    contractor_member_id: UUID
    due_at: datetime | None = None


class InstallationAssignmentCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class InstallationAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    plate_id: UUID
    contractor_id: UUID
    contractor_member_id: UUID
    assigned_by: UUID
    assigned_at: datetime
    due_at: datetime | None
    status: str
    cancelled_by: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime


class InstallationAssignmentSubmit(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    captured_at: datetime
    notes: str | None = None
