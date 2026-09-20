from uuid import UUID

from sqlalchemy.orm import Session

from app.models.landlord import Landlord


class LandlordRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, landlord_id: UUID) -> Landlord | None:
        return self.db.get(Landlord, landlord_id)

    def get_by_user_id(self, user_id: UUID) -> Landlord | None:
        return self.db.query(Landlord).filter(
            Landlord.user_id == user_id
        ).first()

    def add(self, landlord: Landlord) -> Landlord:
        self.db.add(landlord)
        self.db.flush()

        return landlord
