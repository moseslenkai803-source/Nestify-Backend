from uuid import UUID

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate


class AddressPlateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_plate_code(self, plate_code: str) -> AddressPlate | None:
        return (
            self.db.query(AddressPlate)
            .filter(AddressPlate.plate_code == plate_code)
            .first()
        )

    def get_by_property_id(self, property_id: UUID) -> AddressPlate | None:
        return (
            self.db.query(AddressPlate)
            .filter(AddressPlate.property_id == property_id)
            .first()
        )

    def get_unactivated(self) -> list[AddressPlate]:
        return (
            self.db.query(AddressPlate)
            .filter(AddressPlate.status == "unactivated")
            .all()
        )
