from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)
from app.schemas.auth import (
    CurrentUserResponse,
    LandlordRegistrationRequest,
    LandlordRegistrationResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.registration_service import RegistrationService
from app.services.user_service import UserService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=LandlordRegistrationResponse,
    status_code=201,
)
def register_landlord(
    registration_data: LandlordRegistrationRequest,
    db: Session = Depends(get_db),
):
    service = RegistrationService(db)

    try:
        user, landlord = service.register_landlord(
            email=registration_data.email,
            password=registration_data.password,
            display_name=registration_data.display_name,
            phone=registration_data.phone,
            landlord_type=registration_data.landlord_type,
        )

        return LandlordRegistrationResponse(
            user_id=user.id,
            landlord_id=landlord.id,
            email=user.email,
            display_name=landlord.display_name,
            phone=landlord.phone,
            landlord_type=landlord.landlord_type,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    service = UserService(db)

    try:
        user = service.authenticate_user(
            email=login_data.email,
            password=login_data.password,
        )

        access_token = create_access_token(
            subject=str(user.id),
        )

        return TokenResponse(
            access_token=access_token,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permissions: list[str] = []

    if current_user.role == "admin":
        permissions.append("admin")

    elif current_user.role == "employee":
        employee = EmployeeRepository(db).get_by_user_id(
            current_user.id
        )

        if employee is not None and employee.ended_at is None:
            clearances = (
                EmployeeClearanceRepository(db)
                .get_active_by_employee_id(employee.id)
            )
            permissions.extend(
                sorted({item.clearance for item in clearances})
            )

    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "clearance": current_user.clearance,
        "is_active": current_user.is_active,
        "permissions": permissions,
    }
