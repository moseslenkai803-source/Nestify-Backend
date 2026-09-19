from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PropertyCreate(BaseModel):
    name: str
    property_type: str


class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    landlord_id: UUID
    property_code: str
    name: str
    property_type: str
    status: str
