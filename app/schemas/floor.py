from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FloorCreate(BaseModel):
    floor_number: str
    name: str | None = None


class FloorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    building_id: UUID
    floor_number: str
    name: str | None
    status: str
