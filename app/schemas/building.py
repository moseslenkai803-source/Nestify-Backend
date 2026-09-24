from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BuildingCreate(BaseModel):
    building_number: str
    name: str | None = None


class BuildingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    building_number: str
    name: str | None
    status: str
