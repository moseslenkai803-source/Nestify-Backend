from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyLocationCreate(BaseModel):
    latitude: float
    longitude: float
    source: str
    capture_method: str
    accuracy_meters: float | None = Field(default=None, ge=0)
    captured_at: datetime


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
