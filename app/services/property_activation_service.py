import uuid

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.repositories.property_address_repository import PropertyAddressRepository
from app.services.address_plate_service import AddressPlateService
from app.services.property_service import PropertyService


class PropertyActivationService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_service = AddressPlateService(db)
        self.property_service = PropertyService(db)
        self.property_address_repository = PropertyAddressRepository(db)

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

        plate = self.address_plate_service.link_plate_to_property(
            plate_code=plate_code,
            property_id=property.id,
        )

        property.status = "active"
        self.db.flush()

        return plate
