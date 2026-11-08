from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property_location_verification import (
    PropertyLocationVerification,
)


class PropertyLocationVerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_location_id(
        self,
        location_id: UUID,
    ) -> PropertyLocationVerification | None:
        statement = select(PropertyLocationVerification).where(
            PropertyLocationVerification.location_id == location_id
        )
        return self.db.scalar(statement)

    def add(
        self,
        verification: PropertyLocationVerification,
    ) -> PropertyLocationVerification:
        self.db.add(verification)
        self.db.flush()
        return verification
