from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LandlordRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    phone: str
    landlord_type: str = "individual"


class LandlordRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    landlord_id: UUID
    email: EmailStr
    display_name: str
    phone: str
    landlord_type: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    clearance: str | None
    is_active: bool
    permissions: list[str] = Field(default_factory=list)
