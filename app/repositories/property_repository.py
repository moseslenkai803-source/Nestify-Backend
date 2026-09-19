from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property import Property


class PropertyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, property_id: UUID) -> Property | None:
        return self.db.get(Property, property_id)
