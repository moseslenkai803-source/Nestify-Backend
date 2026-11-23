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


class EmployeeInvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class EmployeeInvitationAcceptResponse(BaseModel):
    user_id: UUID
    employee_id: UUID
    email: EmailStr
    message: str = "Employee account created successfully"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetVerifyRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class PasswordResetVerifyResponse(BaseModel):
    reset_grant: str
    message: str = "Verification successful."


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    reset_grant: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordResetRequestResponse(BaseModel):
    message: str = (
        "If an account exists for that email, "
        "a verification code will be sent."
    )


class PasswordResetConfirmResponse(BaseModel):
    message: str = "Your password has been changed successfully."
