from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ManufacturingOrderCreate(BaseModel):
    quantity: int = Field(gt=0)


class ManufacturingOrderCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cancellation reason must not be blank")
        return value


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
    cancelled_by: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
