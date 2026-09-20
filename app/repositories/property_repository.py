from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property import Property


class PropertyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, property_id: UUID) -> Property | None:
        return self.db.get(Property, property_id)

    def get_by_id_for_landlord(
        self,
        property_id: UUID,
        landlord_id: UUID,
    ) -> Property | None:
        return (
            self.db.query(Property)
            .filter(
                Property.id == property_id,
                Property.landlord_id == landlord_id,
            )
            .first()
        )

    def get_by_landlord_id(self, landlord_id: UUID) -> list[Property]:
        return (
            self.db.query(Property)
            .filter(Property.landlord_id == landlord_id)
            .all()
        )

    def add(self, property: Property) -> Property:
        self.db.add(property)
        self.db.flush()

        return property
