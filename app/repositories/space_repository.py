from uuid import UUID

from sqlalchemy.orm import Session

from app.models.space import Space


class SpaceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, space_id: UUID) -> Space | None:
        return self.db.get(Space, space_id)

    def get_by_floor_id(self, floor_id: UUID) -> list[Space]:
        return (
            self.db.query(Space)
            .filter(Space.floor_id == floor_id)
            .all()
        )

    def get_by_floor_and_number(
        self,
        floor_id: UUID,
        space_number: str,
    ) -> Space | None:
        return (
            self.db.query(Space)
            .filter(
                Space.floor_id == floor_id,
                Space.space_number == space_number,
            )
            .first()
        )

    def add(self, space: Space) -> Space:
        self.db.add(space)
        self.db.flush()
        return space
