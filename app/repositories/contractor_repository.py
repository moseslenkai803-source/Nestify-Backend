from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contractor import Contractor


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
