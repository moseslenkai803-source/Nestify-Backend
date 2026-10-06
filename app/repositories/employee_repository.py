from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.user import User


class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        employee: Employee,
    ) -> Employee:
        self.db.add(employee)
        self.db.flush()

        return employee

    def get_by_id(
        self,
        employee_id: UUID,
    ) -> Employee | None:
        return self.db.get(Employee, employee_id)

    def get_by_id_for_update(
        self,
        employee_id: UUID,
    ) -> Employee | None:
        statement = (
            select(Employee)
            .where(Employee.id == employee_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> Employee | None:
        statement = (
            select(Employee)
            .where(Employee.user_id == user_id)
        )
        return self.db.scalar(statement)

    def get_by_employee_number(
        self,
        employee_number: str,
    ) -> Employee | None:
        statement = (
            select(Employee)
            .where(Employee.employee_number == employee_number)
        )
        return self.db.scalar(statement)

    def get_all(self) -> list[Employee]:
        return (
            self.db.query(Employee)
            .order_by(
                Employee.created_at.desc(),
                Employee.id.desc(),
            )
            .all()
        )

    def get_active(self) -> list[Employee]:
        statement = (
            select(Employee)
            .join(User, User.id == Employee.user_id)
            .where(
                User.is_active.is_(True),
                Employee.ended_at.is_(None),
            )
            .order_by(
                Employee.created_at.desc(),
                Employee.id.desc(),
            )
        )
        return list(self.db.scalars(statement).all())
