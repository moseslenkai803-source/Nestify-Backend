import uuid

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.models.property import Property
from app.repositories.property_address_repository import PropertyAddressRepository
from app.services.address_plate_service import AddressPlateService
from app.services.property_service import PropertyService


class PropertyActivationService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_service = AddressPlateService(db)
        self.property_service = PropertyService(db)
        self.property_address_repository = PropertyAddressRepository(db)

    def get_property_for_landlord(
        self,
        property_id: uuid.UUID,
        landlord_id: uuid.UUID,
    ) -> Property:
        property = self.property_service.get_property_for_landlord(
            property_id=property_id,
            landlord_id=landlord_id,
        )

        return property

    def activate_property(
        self,
        property_id: uuid.UUID,
        landlord_id: uuid.UUID,
        plate_code: str,
    ) -> AddressPlate:
        property = self.property_service.get_property_for_landlord(
            property_id=property_id,
            landlord_id=landlord_id,
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
