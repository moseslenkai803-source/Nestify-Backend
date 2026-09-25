import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.property_address_repository import PropertyAddressRepository
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.services.property_service import PropertyService


class PropertyActivationService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)
        self.property_service = PropertyService(db)
        self.property_address_repository = PropertyAddressRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)

    def activate_property(
        self,
        property_id: uuid.UUID,
        plate_code: str,
    ) -> AddressPlate:
        property = self.property_service.property_repository.get_by_id(
            property_id
        )

        if property is None:
            raise ValueError("Property not found")

        if property.status == "active":
            raise ValueError("Property is already active")

        if property.status != "verified":
            raise ValueError(
                "Only verified properties can be activated"
            )

        address = self.property_address_repository.get_by_property_id(
            property.id
        )

        if address is None:
            raise ValueError(
                "Property must have an address before activation"
            )

        plate = self.address_plate_repository.get_by_plate_code(
            plate_code
        )

        if plate is None:
            raise ValueError("Plate not found")

        if plate.property_id != property.id:
            raise ValueError(
                "Plate is not allocated to this property"
            )

        if plate.status == "active":
            raise ValueError("Plate is already active")

        latest_event = self.lifecycle_service.get_latest_event(
            plate.id
        )

        if latest_event is None or latest_event.event_type != "verified":
            raise ValueError(
                "Only verified plates can be activated"
            )

        plate.status = "active"
        plate.activated_at = datetime.now(UTC)

        self.lifecycle_service.record_event(
            plate_id=plate.id,
            event_type="activated",
            performed_by=latest_event.performed_by,
        )

        property.status = "active"

        self.db.flush()

        return plate
