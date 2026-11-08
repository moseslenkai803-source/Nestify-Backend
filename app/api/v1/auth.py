from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.rate_limit import rate_limit_dependency
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)
from app.schemas.auth import (
    CurrentUserResponse,
    EmployeeInvitationAcceptRequest,
    EmployeeInvitationAcceptResponse,
    LandlordRegistrationRequest,
    LandlordRegistrationResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.registration_service import RegistrationService
from app.services.employee_invitation_service import EmployeeInvitationService
from app.services.user_service import UserService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=LandlordRegistrationResponse,
    status_code=201,
    dependencies=[
        Depends(rate_limit_dependency(
            policy_name="auth-register",
            allow_emergency_fallback=False,
            limit=5,
            window_seconds=60,
        )),
        Depends(rate_limit_dependency(
            policy_name="auth-register-account",
            allow_emergency_fallback=False,
            limit=3,
            window_seconds=3600,
            identity_field="email",
        )),
    ],
)
def register_landlord(
    registration_data: LandlordRegistrationRequest,
    db: Session = Depends(get_db, scope='function'),
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
    "/employee-invitations/accept",
    response_model=EmployeeInvitationAcceptResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_dependency(
        policy_name="auth-invitation-accept",
        allow_emergency_fallback=False,
        limit=5,
        window_seconds=60,
    ))],
)
def accept_employee_invitation(
    invitation_data: EmployeeInvitationAcceptRequest,
    db: Session = Depends(get_db, scope='function'),
):
    service = EmployeeInvitationService(db)

    try:
        user, employee = service.accept_invitation(
            token=invitation_data.token,
            password=invitation_data.password,
        )
    except ValueError as exc:
        db.rollback()
        detail = str(exc)
        status_code = 400

        if detail in {
            "Invitation is invalid or has expired",
            "Invitation has already been used",
        }:
            status_code = 400

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        ) from exc

    return EmployeeInvitationAcceptResponse(
        user_id=user.id,
        employee_id=employee.id,
        email=user.email,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[
        Depends(rate_limit_dependency(
            policy_name="auth-login",
            allow_emergency_fallback=False,
            limit=10,
            window_seconds=60,
        )),
        Depends(rate_limit_dependency(
            policy_name="auth-login-account",
            allow_emergency_fallback=False,
            limit=5,
            window_seconds=300,
            identity_field="email",
        )),
    ],
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db, scope='function'),
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
    db: Session = Depends(get_db, scope='function'),
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
