from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee_invitation import EmployeeInvitation


class EmployeeInvitationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_token_hash(
        self,
        token_hash: str,
    ) -> EmployeeInvitation | None:
        statement = select(EmployeeInvitation).where(
            EmployeeInvitation.token_hash == token_hash
        )
        return self.db.scalar(statement)

    def get_by_token_hash_for_update(
        self,
        token_hash: str,
    ) -> EmployeeInvitation | None:
        statement = (
            select(EmployeeInvitation)
            .where(EmployeeInvitation.token_hash == token_hash)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_pending_by_email(
        self,
        email: str,
    ) -> list[EmployeeInvitation]:
        statement = select(EmployeeInvitation).where(
            EmployeeInvitation.email == email,
            EmployeeInvitation.redeemed_at.is_(None),
        )
        return list(self.db.scalars(statement).all())

    def get_pending_by_employee_number(
        self,
        employee_number: str,
    ) -> list[EmployeeInvitation]:
        statement = select(EmployeeInvitation).where(
            EmployeeInvitation.employee_number == employee_number,
            EmployeeInvitation.redeemed_at.is_(None),
        )
        return list(self.db.scalars(statement).all())

    def add(
        self,
        invitation: EmployeeInvitation,
    ) -> EmployeeInvitation:
        self.db.add(invitation)
        self.db.flush()
        return invitation
