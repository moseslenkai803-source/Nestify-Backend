from uuid import UUID

from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.user import User
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


class PlateOperationsAuthorizationService:
    """Central authorization policy for Nestify plate operations."""

    def __init__(self, db: Session):
        self.user_repository = UserRepository(db)
        self.employee_repository = EmployeeRepository(db)
        self.employee_clearance_repository = EmployeeClearanceRepository(db)
        self.property_authorization_service = PropertyAuthorizationService(db)

    def require_authorized_user(self, user_id: UUID) -> User:
        user_snapshot = self.user_repository.get_by_id(user_id)

        if user_snapshot is None:
            raise ValueError("User not found")

        employee = None
        if user_snapshot.role == "employee":
            employee = self.employee_repository.get_by_user_id_for_update(
                user_id
            )

        user = self.user_repository.get_by_id_for_update(user_id)

        if user is None:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("User account is inactive")

        # Rechecking the role after acquiring the row lock prevents a stale
        # pre-lock role snapshot from authorizing a concurrent role change.
        # Administrators have an explicit operational exception.
        if user_snapshot.role == "admin" and user.role == "admin":
            return user

        if (
            user_snapshot.role != "employee"
            or user.role != "employee"
        ):
            raise ValueError("Only Nestify employees can perform plate operations")

        if employee is None:
            raise ValueError("Employee record not found")

        if employee.ended_at is not None:
            raise ValueError("Employee is terminated")

        clearance = (
            self.employee_clearance_repository
            .get_by_employee_and_clearance_for_update(
                employee.id,
                "plate_operations",
            )
        )

        if clearance is None or not clearance.is_active:
            raise ValueError(
                "Active plate_operations employee clearance is required"
            )

        return user

    def authorize_property(
        self,
        user_id: UUID,
        property_id: UUID,
    ):
        user = self.require_authorized_user(user_id)
        property_record = (
            self.property_authorization_service.property_repository
            .get_by_id(property_id)
        )

        if property_record is None:
            raise ValueError("Property not found")

        if user.role == "admin":
            return property_record

        property_access = (
            self.property_authorization_service.property_access_repository
            .get_by_user_property_type_for_update(
                user_id=user.id,
                property_id=property_id,
                access_type=PropertyAction.PLATE_OPERATIONS.value,
            )
        )

        if property_access is None or not property_access.is_active:
            raise ValueError("User is not authorized for this property")

        return property_record
