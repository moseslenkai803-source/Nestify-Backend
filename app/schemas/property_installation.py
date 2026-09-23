from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyInstallationCreate(BaseModel):
    plate_id: UUID
    latitude: float
    longitude: float
    accuracy_meters: float | None = Field(default=None, ge=0)
    captured_at: datetime
    notes: str | None = None


class PropertyInstallationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    plate_id: UUID
    installer_id: UUID
    latitude: float
    longitude: float
    accuracy_meters: float | None
    captured_at: datetime
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
