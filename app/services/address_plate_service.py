import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.property_repository import PropertyRepository


class AddressPlateService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)
        self.property_repository = PropertyRepository(db)

    def create_plate(
        self,
        manufacturing_order_id: uuid.UUID | None = None,
    ) -> AddressPlate:
        plate_code = f"PLATE-{uuid.uuid4().hex[:12].upper()}"

        plate = AddressPlate(
            plate_code=plate_code,
            status="unactivated",
            manufacturing_order_id=manufacturing_order_id,
        )

        self.db.add(plate)
        self.db.flush()

        return plate

    def get_plate_by_code(self, plate_code: str) -> AddressPlate | None:
        return self.address_plate_repository.get_by_plate_code(
            plate_code
        )

    def verify_plate(self, plate_code: str) -> AddressPlate:
        plate = self.address_plate_repository.get_by_plate_code(
            plate_code
        )

        if plate is None:
            raise ValueError("Plate not found")

        if plate.status != "unactivated":
            raise ValueError(
                "Plate cannot be verified in its current status"
            )

        plate.status = "verified"
        plate.verified_at = datetime.now(UTC)

        self.db.flush()

        return plate

    def link_plate_to_property(
        self,
        plate_code: str,
        property_id: uuid.UUID,
    ) -> AddressPlate:
        plate = self.address_plate_repository.get_by_plate_code(
            plate_code
        )

        if plate is None:
            raise ValueError("Plate not found")

        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        if plate.property_id is not None:
            raise ValueError(
                "Plate is already linked to a property"
            )

        if plate.status != "verified":
            raise ValueError(
                "Only verified plates can be linked to a property"
            )

        existing_plate = (
            self.address_plate_repository.get_by_property_id(
                property_id
            )
        )

        if existing_plate is not None:
            raise ValueError(
                "Property already has a primary address plate"
            )

        plate.property_id = property_id
        plate.status = "active"
        plate.activated_at = datetime.now(UTC)

        self.db.flush()

        return plate
