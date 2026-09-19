import uuid

from sqlalchemy.orm import Session

from app.models.property import Property
from app.repositories.property_repository import PropertyRepository


class PropertyService:
    def __init__(self, db: Session):
        self.repository = PropertyRepository(db)

    def create_property(
        self,
        landlord_id: uuid.UUID,
        name: str,
        property_type: str,
    ) -> Property:
        property_code = f"NEST-{uuid.uuid4().hex[:12].upper()}"

        property = Property(
            landlord_id=landlord_id,
            property_code=property_code,
            name=name,
            property_type=property_type,
            status="draft",
        )

        return self.repository.add(property)
