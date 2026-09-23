from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_location import PropertyLocation


class PropertyLocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, property_location: PropertyLocation) -> PropertyLocation:
        self.db.add(property_location)
        self.db.flush()
        return property_location

    def get_by_id(self, location_id: UUID) -> PropertyLocation | None:
        return self.db.get(PropertyLocation, location_id)

    def get_by_property_id(
        self,
        property_id: UUID,
    ) -> PropertyLocation | None:
        return (
            self.db.query(PropertyLocation)
            .filter(PropertyLocation.property_id == property_id)
            .first()
        )
