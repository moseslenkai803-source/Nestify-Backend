import uuid
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
        activated_by: uuid.UUID,
    ) -> AddressPlate:
        property = (
            self.property_service.property_repository.get_by_id_for_update(
                property_id
            )
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

        plate = self.address_plate_repository.get_by_id_for_update(
            plate.id
        )

        if plate is None:
            raise ValueError("Plate not found")

        if plate.property_id != property.id:
            raise ValueError(
                "Plate is not allocated to this property"
            )

        plate = self.lifecycle_service.activate_plate(
            plate_id=plate.id,
            performed_by=activated_by,
        )

        property.status = "active"

        self.db.flush()

        return plate
