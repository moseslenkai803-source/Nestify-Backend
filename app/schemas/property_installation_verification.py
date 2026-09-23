from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PropertyInstallationVerificationCreate(BaseModel):
    status: Literal["verified", "rejected"]
    notes: str | None = None


class PropertyInstallationVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    installation_id: UUID
    verified_by: UUID
    status: str
    verified_at: datetime
    notes: str | None
    created_at: datetime
