from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contractor_member import ContractorMember
from app.models.user import User


class ContractorMemberRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        contractor_member: ContractorMember,
    ) -> ContractorMember:
        self.db.add(contractor_member)
        self.db.flush()

        return contractor_member

    def get_by_id_for_update(
        self,
        contractor_member_id: UUID,
    ) -> ContractorMember | None:
        statement = (
            select(ContractorMember)
            .where(ContractorMember.id == contractor_member_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_contractor_and_user_for_update(
        self,
        contractor_id: UUID,
        user_id: UUID,
    ) -> ContractorMember | None:
        statement = (
            select(ContractorMember)
            .where(
                ContractorMember.contractor_id == contractor_id,
                ContractorMember.user_id == user_id,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_active_by_contractor_and_user(
        self,
        contractor_id: UUID,
        user_id: UUID,
    ) -> ContractorMember | None:
        return (
            self.db.query(ContractorMember)
            .filter(
                ContractorMember.contractor_id == contractor_id,
                ContractorMember.user_id == user_id,
                ContractorMember.is_active.is_(True),
            )
            .first()
        )

    def get_active_by_contractor_id(
        self,
        contractor_id: UUID,
    ) -> list[ContractorMember]:
        return (
            self.db.query(ContractorMember)
            .filter(
                ContractorMember.contractor_id == contractor_id,
                ContractorMember.is_active.is_(True),
            )
            .order_by(
                ContractorMember.created_at.desc(),
                ContractorMember.id.desc(),
            )
            .all()
        )

    def get_active_with_user_email_by_contractor_id(
        self,
        contractor_id: UUID,
    ) -> list[tuple[ContractorMember, str]]:
        statement = (
            select(ContractorMember, User.email)
            .join(User, User.id == ContractorMember.user_id)
            .where(
                ContractorMember.contractor_id == contractor_id,
                ContractorMember.is_active.is_(True),
                User.is_active.is_(True),
                User.role == "contractor",
            )
            .order_by(
                ContractorMember.created_at.desc(),
                ContractorMember.id.desc(),
            )
        )

        return list(self.db.execute(statement).all())

    def get_by_contractor_id(
        self,
        contractor_id: UUID,
    ) -> list[ContractorMember]:
        return (
            self.db.query(ContractorMember)
            .filter(ContractorMember.contractor_id == contractor_id)
            .order_by(ContractorMember.created_at.desc())
            .all()
        )

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> list[ContractorMember]:
        return (
            self.db.query(ContractorMember)
            .filter(ContractorMember.user_id == user_id)
            .order_by(ContractorMember.created_at.desc())
            .all()
        )

    def deactivate(
        self,
        contractor_member: ContractorMember,
    ) -> ContractorMember:
        contractor_member.is_active = False
        self.db.flush()

        return contractor_member
