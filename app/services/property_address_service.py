import uuid

from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.repositories.property_address_repository import PropertyAddressRepository
from app.repositories.property_repository import PropertyRepository


class PropertyAddressService:
    def __init__(self, db: Session):
        self.property_repository = PropertyRepository(db)
        self.property_address_repository = PropertyAddressRepository(db)
        self.db = db

    def get_property_for_landlord(
        self,
        property_id: uuid.UUID,
        landlord_id: uuid.UUID,
    ) -> Property:
        property = self.property_repository.get_by_id_for_landlord(
            property_id=property_id,
            landlord_id=landlord_id,
        )

        if property is None:
            raise ValueError("Property not found")

        return property

    def get_address(
        self,
        property_id: uuid.UUID,
    ) -> PropertyAddress:
        address = self.property_address_repository.get_by_property_id(
            property_id
        )

        if address is None:
            raise ValueError("Property address not found")

        return address

    def create_address(
        self,
        property_id: uuid.UUID,
        formatted_address: str | None = None,
        county: str | None = None,
        sub_county: str | None = None,
        locality: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> PropertyAddress:
        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        existing_address = self.property_address_repository.get_by_property_id(
            property_id
        )

        if existing_address is not None:
            raise ValueError(
                "Property already has an address"
            )

        location = None

        if latitude is not None and longitude is not None:
            location = WKTElement(
                f"POINT({longitude} {latitude})",
                srid=4326,
            )

        address = PropertyAddress(
            property_id=property_id,
            formatted_address=formatted_address,
            county=county,
            sub_county=sub_county,
            locality=locality,
            latitude=latitude,
            longitude=longitude,
            location=location,
        )

        self.db.add(address)
        self.db.flush()

        return address
