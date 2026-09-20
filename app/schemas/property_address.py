from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PropertyAddressCreate(BaseModel):
    formatted_address: str | None = None
    county: str | None = None
    sub_county: str | None = None
    locality: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class PropertyAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    formatted_address: str | None
    county: str | None
    sub_county: str | None
    locality: str | None
    latitude: float | None
    longitude: float | None
