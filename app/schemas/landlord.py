import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class LandlordOnboardRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255, description="The name displayed publicly for the landlord account.")
    phone: str = Field(..., min_length=1, max_length=30, description="The primary operational telephone connection string.")
    landlord_type: Literal["individual", "corporate"] = Field("individual", description="The categorization layout tracking profile invariants.")


class LandlordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    phone: str
    landlord_type: str
    created_at: datetime
    updated_at: datetime
