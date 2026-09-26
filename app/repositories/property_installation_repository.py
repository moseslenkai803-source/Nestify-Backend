import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property_installation import PropertyInstallation


class PropertyInstallationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        installation: PropertyInstallation,
    ) -> PropertyInstallation:
        self.db.add(installation)
        self.db.flush()
        return installation

    def get_by_id(
        self,
        installation_id: uuid.UUID,
    ) -> PropertyInstallation | None:
        return self.db.scalar(
            select(PropertyInstallation).where(
                PropertyInstallation.id == installation_id
            )
        )

    def get_by_id_for_update(
        self,
        installation_id: uuid.UUID,
    ) -> PropertyInstallation | None:
        statement = (
            select(PropertyInstallation)
            .where(PropertyInstallation.id == installation_id)
            .with_for_update()
        )

        return self.db.scalar(statement)

    def get_by_property_id(
        self,
        property_id: uuid.UUID,
    ) -> PropertyInstallation | None:
        return self.db.scalar(
            select(PropertyInstallation)
            .where(PropertyInstallation.property_id == property_id)
            .order_by(PropertyInstallation.created_at.desc())
        )

    def get_by_plate_id(
        self,
        plate_id: uuid.UUID,
    ) -> PropertyInstallation | None:
        return self.db.scalar(
            select(PropertyInstallation)
            .where(PropertyInstallation.plate_id == plate_id)
            .order_by(PropertyInstallation.created_at.desc())
        )
