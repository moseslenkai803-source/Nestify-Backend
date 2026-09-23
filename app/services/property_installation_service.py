import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.property_installation import PropertyInstallation
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.property_installation_repository import (
    PropertyInstallationRepository,
)
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository


class PropertyInstallationService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repository = PropertyRepository(db)
        self.address_plate_repository = AddressPlateRepository(db)
        self.user_repository = UserRepository(db)
        self.property_installation_repository = PropertyInstallationRepository(db)

    def create_installation(
        self,
        property_id: uuid.UUID,
        plate_id: uuid.UUID,
        installer_id: uuid.UUID,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None,
        captured_at: datetime,
        notes: str | None = None,
    ) -> PropertyInstallation:
        property = self.property_repository.get_by_id(property_id)
        if property is None:
            raise ValueError("Property not found")

        plate = self.address_plate_repository.get_by_id(plate_id)
        if plate is None:
            raise ValueError("Address plate not found")

        installer = self.user_repository.get_by_id(installer_id)
        if installer is None:
            raise ValueError("Installer not found")

        if not installer.is_active:
            raise ValueError("Installer is inactive")

        if plate.property_id != property_id:
            raise ValueError("Address plate is not linked to this property")

        if not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")

        if not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

        if accuracy_meters is not None and accuracy_meters < 0:
            raise ValueError("Accuracy must be greater than or equal to 0")

        if captured_at.tzinfo is None:
            raise ValueError("Captured timestamp must be timezone-aware")

        existing_installation = (
            self.property_installation_repository.get_by_property_id(
                property_id
            )
        )

        if (
            existing_installation is not None
            and existing_installation.status == "submitted"
        ):
            raise ValueError(
                "Property already has a submitted installation"
            )

        installation = PropertyInstallation(
            property_id=property_id,
            plate_id=plate_id,
            installer_id=installer_id,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            captured_at=captured_at,
            status="submitted",
            notes=notes,
        )

        return self.property_installation_repository.add(installation)
