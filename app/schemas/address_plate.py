from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AddressPlateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID | None
    plate_code: str
    status: str
    activated_at: datetime | None


class PlateInventoryResponse(BaseModel):
    id: UUID
    plate_code: str
    property_id: UUID | None
    property_code: str | None
    property_name: str | None
    status: str
    lifecycle_status: str | None
    activated_at: datetime | None


class AddressPlateRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    requested_by: UUID
    status: str
    requested_at: datetime
    created_at: datetime
    updated_at: datetime
