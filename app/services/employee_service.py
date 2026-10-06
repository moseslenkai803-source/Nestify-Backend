from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.user import User
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db
        self.employee_repository = EmployeeRepository(db)
        self.employee_clearance_repository = EmployeeClearanceRepository(db)
        self.user_repository = UserRepository(db)

    def create_employee(
        self,
        user_id: UUID,
        employee_number: str,
        department: str,
        position: str,
        clearances: list[str] | None = None,
    ) -> Employee:
        employee_number = employee_number.strip()
        department = department.strip()
        position = position.strip()

        if not employee_number:
            raise ValueError("Employee number is required")

        if not department:
            raise ValueError("Department is required")

        if not position:
            raise ValueError("Position is required")

        user = self.user_repository.get_by_id_for_update(user_id)

        if user is None:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("User is inactive")

        if user.role != "employee":
            raise ValueError("Only employee users can have employee records")

        existing_employee = self.employee_repository.get_by_user_id(user_id)

        if existing_employee is not None:
            raise ValueError("User is already an employee")

        existing_employee_number = (
            self.employee_repository.get_by_employee_number(
                employee_number
            )
        )

        if existing_employee_number is not None:
            raise ValueError("Employee number already exists")

        employee = Employee(
            user_id=user_id,
            employee_number=employee_number,
            department=department,
            position=position,
        )

        self.employee_repository.add(employee)

        requested_clearances = clearances or []
        normalized_clearances = []

        for clearance in requested_clearances:
            normalized_clearance = clearance.strip()

            if not normalized_clearance:
                raise ValueError("Clearance is required")

            if normalized_clearance not in normalized_clearances:
                normalized_clearances.append(normalized_clearance)

        for clearance in normalized_clearances:
            self.employee_clearance_repository.add(
                EmployeeClearance(
                    employee_id=employee.id,
                    clearance=clearance,
                    is_active=True,
                )
            )

        self.db.flush()

        return employee

    def get_employee(
        self,
        employee_id: UUID,
    ) -> Employee:
        employee = self.employee_repository.get_by_id(employee_id)

        if employee is None:
            raise ValueError("Employee not found")

        return employee

    def list_employees(
        self,
        active_only: bool = False,
    ) -> list[Employee]:
        if active_only:
            return self.employee_repository.get_active()

        return self.employee_repository.get_all()

    def list_employee_candidates(self) -> list[User]:
        return self.employee_repository.get_candidate_users()

    def add_clearance(
        self,
        employee_id: UUID,
        clearance: str,
    ) -> EmployeeClearance:
        clearance = clearance.strip()

        if not clearance:
            raise ValueError("Clearance is required")

        employee = self.employee_repository.get_by_id_for_update(
            employee_id
        )

        if employee is None:
            raise ValueError("Employee not found")

        if employee.ended_at is not None:
            raise ValueError("Employee is terminated")

        user = self.user_repository.get_by_id_for_update(
            employee.user_id
        )

        if user is None:
            raise ValueError("Employee user not found")

        if not user.is_active:
            raise ValueError("Employee user is inactive")

        existing = (
            self.employee_clearance_repository
            .get_by_employee_and_clearance(
                employee_id=employee_id,
                clearance=clearance,
            )
        )

        if existing is not None:
            if existing.is_active:
                raise ValueError(
                    "Employee already has this active clearance"
                )

            existing = (
                self.employee_clearance_repository.get_by_id_for_update(
                    existing.id
                )
            )

            if existing is None:
                raise ValueError("Employee clearance not found")

            existing.is_active = True
            self.db.flush()

            return existing

        record = EmployeeClearance(
            employee_id=employee_id,
            clearance=clearance,
            is_active=True,
        )

        return self.employee_clearance_repository.add(record)

    def remove_clearance(
        self,
        employee_id: UUID,
        clearance: str,
    ) -> EmployeeClearance:
        clearance = clearance.strip()

        if not clearance:
            raise ValueError("Clearance is required")

        employee = self.employee_repository.get_by_id_for_update(
            employee_id
        )

        if employee is None:
            raise ValueError("Employee not found")

        if employee.ended_at is not None:
            raise ValueError("Employee is terminated")

        record = (
            self.employee_clearance_repository
            .get_by_employee_and_clearance(
                employee_id=employee_id,
                clearance=clearance,
            )
        )

        if record is None or not record.is_active:
            raise ValueError("Active employee clearance not found")

        record = self.employee_clearance_repository.get_by_id_for_update(
            record.id
        )

        if record is None:
            raise ValueError("Employee clearance not found")

        record.is_active = False
        self.db.flush()

        return record

    def list_clearances(
        self,
        employee_id: UUID,
        active_only: bool = False,
    ) -> list[EmployeeClearance]:
        employee = self.employee_repository.get_by_id(employee_id)

        if employee is None:
            raise ValueError("Employee not found")

        if active_only:
            return (
                self.employee_clearance_repository
                .get_active_by_employee_id(employee_id)
            )

        return self.employee_clearance_repository.get_by_employee_id(
            employee_id
        )

    def terminate_employee(
        self,
        employee_id: UUID,
    ) -> Employee:
        employee = self.employee_repository.get_by_id_for_update(
            employee_id
        )

        if employee is None:
            raise ValueError("Employee not found")

        if employee.ended_at is not None:
            raise ValueError("Employee is already terminated")

        user = self.user_repository.get_by_id_for_update(
            employee.user_id
        )

        if user is None:
            raise ValueError("Employee user not found")

        if not user.is_active:
            raise ValueError("Employee user is already inactive")

        employee.ended_at = datetime.now(UTC)
        user.is_active = False

        clearances = (
            self.employee_clearance_repository
            .get_active_by_employee_id(employee.id)
        )

        for clearance in clearances:
            clearance.is_active = False

        self.db.flush()

        return employee
