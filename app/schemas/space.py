from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SpaceCreate(BaseModel):
    space_number: str
    name: str | None = None
    space_type: str = "general"


class SpaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    floor_id: UUID
    space_number: str
    name: str | None
    space_type: str
    status: str
