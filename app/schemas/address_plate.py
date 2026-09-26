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
    verified_at: datetime | None


class AddressPlateRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    requested_by: UUID
    status: str
    requested_at: datetime
    created_at: datetime
    updated_at: datetime
