import uuid

from sqlalchemy.orm import Session

from app.models.property_verification import PropertyVerification


class PropertyVerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        verification: PropertyVerification,
    ) -> PropertyVerification:
        self.db.add(verification)
        self.db.flush()

        return verification

    def get_by_property_id(
        self,
        property_id: uuid.UUID,
    ) -> list[PropertyVerification]:
        return (
            self.db.query(PropertyVerification)
            .filter(
                PropertyVerification.property_id == property_id,
            )
            .order_by(
                PropertyVerification.created_at.desc(),
            )
            .all()
        )

    def get_latest_by_property_id(
        self,
        property_id: uuid.UUID,
    ) -> PropertyVerification | None:
        return (
            self.db.query(PropertyVerification)
            .filter(
                PropertyVerification.property_id == property_id,
            )
            .order_by(
                PropertyVerification.created_at.desc(),
            )
            .first()
        )
