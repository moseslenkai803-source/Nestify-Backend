from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DispatchCreate(BaseModel):
    plate_ids: list[UUID] = Field(min_length=1)
    destination: str = Field(min_length=1, max_length=255)
    recipient_name: str = Field(min_length=1, max_length=255)
    recipient_phone: str = Field(min_length=1, max_length=50)
    tracking_reference: str | None = Field(
        default=None,
        max_length=100,
    )


class DispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dispatch_code: str
    status: str
    destination: str
    recipient_name: str
    recipient_phone: str
    tracking_reference: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
