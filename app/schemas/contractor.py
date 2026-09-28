from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContractorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contractor_type: str = Field(
        default="company",
        min_length=1,
        max_length=50,
    )
    contact_email: str | None = Field(
        default=None,
        max_length=255,
    )
    contact_phone: str | None = Field(
        default=None,
        max_length=30,
    )


class ContractorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    contractor_type: str
    status: str
    contact_email: str | None
    contact_phone: str | None
    created_at: datetime
    updated_at: datetime


class ContractorMemberCreate(BaseModel):
    user_id: UUID


class ContractorMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contractor_id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
