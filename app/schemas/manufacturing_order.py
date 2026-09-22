from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ManufacturingOrderCreate(BaseModel):
    quantity: int = Field(gt=0)


class ManufacturingOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_code: str
    quantity: int
    status: str
    created_by: UUID
    approved_by: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
