from uuid import UUID

from sqlalchemy.orm import Session

from app.models.building import Building


class BuildingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, building_id: UUID) -> Building | None:
        return self.db.get(Building, building_id)

    def get_by_property_id(self, property_id: UUID) -> list[Building]:
        return (
            self.db.query(Building)
            .filter(Building.property_id == property_id)
            .all()
        )

    def get_by_property_and_number(
        self,
        property_id: UUID,
        building_number: str,
    ) -> Building | None:
        return (
            self.db.query(Building)
            .filter(
                Building.property_id == property_id,
                Building.building_number == building_number,
            )
            .first()
        )

    def add(self, building: Building) -> Building:
        self.db.add(building)
        self.db.flush()
        return building
