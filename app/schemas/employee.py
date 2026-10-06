from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    user_id: UUID
    employee_number: str = Field(
        min_length=1,
        max_length=100,
    )
    department: str = Field(
        min_length=1,
        max_length=100,
    )
    position: str = Field(
        min_length=1,
        max_length=100,
    )
    clearances: list[str] = Field(
        default_factory=list,
    )


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    employee_number: str
    department: str
    position: str
    joined_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EmployeeClearanceCreate(BaseModel):
    clearance: str = Field(
        min_length=1,
        max_length=100,
    )


class EmployeeClearanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    clearance: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
