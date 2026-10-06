from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contractor import Contractor
from app.models.user import User


class ContractorRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        contractor: Contractor,
    ) -> Contractor:
        self.db.add(contractor)
        self.db.flush()

        return contractor

    def get_by_id(
        self,
        contractor_id: UUID,
    ) -> Contractor | None:
        return self.db.get(Contractor, contractor_id)

    def get_by_id_for_update(
        self,
        contractor_id: UUID,
    ) -> Contractor | None:
        statement = (
            select(Contractor)
            .where(Contractor.id == contractor_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_all(self) -> list[Contractor]:
        return (
            self.db.query(Contractor)
            .order_by(
                Contractor.created_at.desc(),
                Contractor.id.desc(),
            )
            .all()
        )

    def get_candidate_users(self) -> list[User]:
        statement = (
            select(User)
            .where(
                User.role == "contractor",
                User.is_active.is_(True),
            )
            .order_by(
                User.created_at.asc(),
                User.id.asc(),
            )
        )

        return list(self.db.scalars(statement).all())

    def get_active(self) -> list[Contractor]:
        return (
            self.db.query(Contractor)
            .filter(Contractor.status == "active")
            .order_by(
                Contractor.created_at.desc(),
                Contractor.id.desc(),
            )
            .all()
        )
