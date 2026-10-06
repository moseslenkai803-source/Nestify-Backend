from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee_clearance import EmployeeClearance


class EmployeeClearanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        clearance: EmployeeClearance,
    ) -> EmployeeClearance:
        self.db.add(clearance)
        self.db.flush()

        return clearance

    def get_by_id(
        self,
        clearance_id: UUID,
    ) -> EmployeeClearance | None:
        return self.db.get(EmployeeClearance, clearance_id)

    def get_by_id_for_update(
        self,
        clearance_id: UUID,
    ) -> EmployeeClearance | None:
        statement = (
            select(EmployeeClearance)
            .where(EmployeeClearance.id == clearance_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_employee_id(
        self,
        employee_id: UUID,
    ) -> list[EmployeeClearance]:
        return (
            self.db.query(EmployeeClearance)
            .filter(
                EmployeeClearance.employee_id == employee_id,
            )
            .order_by(
                EmployeeClearance.created_at.asc(),
                EmployeeClearance.id.asc(),
            )
            .all()
        )

    def get_active_by_employee_id(
        self,
        employee_id: UUID,
    ) -> list[EmployeeClearance]:
        return (
            self.db.query(EmployeeClearance)
            .filter(
                EmployeeClearance.employee_id == employee_id,
                EmployeeClearance.is_active.is_(True),
            )
            .order_by(
                EmployeeClearance.created_at.asc(),
                EmployeeClearance.id.asc(),
            )
            .all()
        )

    def get_by_employee_and_clearance(
        self,
        employee_id: UUID,
        clearance: str,
    ) -> EmployeeClearance | None:
        statement = (
            select(EmployeeClearance)
            .where(
                EmployeeClearance.employee_id == employee_id,
                EmployeeClearance.clearance == clearance,
            )
        )
        return self.db.scalar(statement)
