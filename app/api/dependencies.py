from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.landlord import Landlord
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.landlord_repository import LandlordRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        ) from exc

    subject = payload.get("sub")

    if subject is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        ) from exc

    user_repository = UserRepository(db)

    user = user_repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User account is inactive",
        )

    return user


def require_employee(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "employee":
        raise HTTPException(
            status_code=403,
            detail="Employee access required",
        )

    return current_user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    return current_user


def require_employee_clearance(
    required_clearance: str,
):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role == "admin":
            return current_user

        if current_user.role != "employee":
            raise HTTPException(
                status_code=403,
                detail="Employee access required",
            )

        employee_repository = EmployeeRepository(db)
        employee_clearance_repository = EmployeeClearanceRepository(db)

        employee = employee_repository.get_by_user_id(
            current_user.id
        )

        if employee is None or employee.ended_at is not None:
            raise HTTPException(
                status_code=403,
                detail="Employee access required",
            )

        active_clearances = (
            employee_clearance_repository
            .get_active_by_employee_id(employee.id)
        )

        if not any(
            clearance.clearance == required_clearance
            for clearance in active_clearances
        ):
            raise HTTPException(
                status_code=403,
                detail="Insufficient employee clearance",
            )

        return current_user

    return dependency


def get_current_landlord(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Landlord:
    if current_user.role != "landlord":
        raise HTTPException(
            status_code=403,
            detail="Landlord access required",
        )

    landlord_repository = LandlordRepository(db)

    landlord = landlord_repository.get_by_user_id(
        current_user.id
    )

    if landlord is None:
        raise HTTPException(
            status_code=404,
            detail="Landlord profile not found",
        )

    return landlord
