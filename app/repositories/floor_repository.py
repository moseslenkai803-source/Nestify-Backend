from uuid import UUID

from sqlalchemy.orm import Session

from app.models.floor import Floor


class FloorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, floor_id: UUID) -> Floor | None:
        return self.db.get(Floor, floor_id)

    def get_by_building_id(self, building_id: UUID) -> list[Floor]:
        return (
            self.db.query(Floor)
            .filter(Floor.building_id == building_id)
            .all()
        )

    def get_by_building_and_number(
        self,
        building_id: UUID,
        floor_number: str,
    ) -> Floor | None:
        return (
            self.db.query(Floor)
            .filter(
                Floor.building_id == building_id,
                Floor.floor_number == floor_number,
            )
            .first()
        )

    def add(self, floor: Floor) -> Floor:
        self.db.add(floor)
        self.db.flush()
        return floor
