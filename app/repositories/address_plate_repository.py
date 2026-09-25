from uuid import UUID

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate


class AddressPlateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, plate_id: UUID) -> AddressPlate | None:
        return self.db.get(AddressPlate, plate_id)

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

    def get_available_for_allocation(self) -> list[AddressPlate]:
        return (
            self.db.query(AddressPlate)
            .filter(
                AddressPlate.status == "unactivated",
                AddressPlate.property_id.is_(None),
            )
            .order_by(AddressPlate.created_at.asc())
            .all()
        )

    def get_by_manufacturing_order_id(
        self,
        manufacturing_order_id: UUID,
    ) -> list[AddressPlate]:
        return (
            self.db.query(AddressPlate)
            .filter(
                AddressPlate.manufacturing_order_id == manufacturing_order_id,
            )
            .order_by(
                AddressPlate.created_at.asc(),
            )
            .all()
        )

    def get_active_by_property_id(
        self,
        property_id: UUID,
    ) -> AddressPlate | None:
        return (
            self.db.query(AddressPlate)
            .filter(
                AddressPlate.property_id == property_id,
                AddressPlate.status == "active",
            )
            .first()
        )
