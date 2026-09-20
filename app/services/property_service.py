import uuid

from sqlalchemy.orm import Session

from app.models.property import Property
from app.repositories.landlord_repository import LandlordRepository
from app.repositories.property_repository import PropertyRepository


class PropertyService:
    def __init__(self, db: Session):
        self.property_repository = PropertyRepository(db)
        self.landlord_repository = LandlordRepository(db)

    def create_property(
        self,
        landlord_id: uuid.UUID,
        name: str,
        property_type: str,
    ) -> Property:
        landlord = self.landlord_repository.get_by_id(landlord_id)

        if landlord is None:
            raise ValueError("Landlord not found")

        property_code = f"NEST-{uuid.uuid4().hex[:12].upper()}"

        property = Property(
            landlord_id=landlord_id,
            property_code=property_code,
            name=name,
            property_type=property_type,
            status="draft",
        )

        return self.property_repository.add(property)


    def get_property(
        self,
        property_id: uuid.UUID,
    ) -> Property:
        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        return property

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

    def list_properties(
        self,
        landlord_id: uuid.UUID,
    ) -> list[Property]:
        landlord = self.landlord_repository.get_by_id(landlord_id)

        if landlord is None:
            raise ValueError("Landlord not found")

        return self.property_repository.get_by_landlord_id(
            landlord_id
        )
