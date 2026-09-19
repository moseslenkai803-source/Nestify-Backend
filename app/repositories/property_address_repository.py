from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_address import PropertyAddress


class PropertyAddressRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, address_id: UUID) -> PropertyAddress | None:
        return self.db.get(PropertyAddress, address_id)

    def get_by_property_id(
        self,
        property_id: UUID,
    ) -> PropertyAddress | None:
        return (
            self.db.query(PropertyAddress)
            .filter(PropertyAddress.property_id == property_id)
            .first()
        )
