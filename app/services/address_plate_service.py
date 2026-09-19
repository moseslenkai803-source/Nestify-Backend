import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.repositories.address_plate_repository import AddressPlateRepository


class AddressPlateService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)

    def create_plate(self) -> AddressPlate:
        plate_code = f"PLATE-{uuid.uuid4().hex[:12].upper()}"

        plate = AddressPlate(
            plate_code=plate_code,
            status="unactivated",
        )

        self.db.add(plate)
        self.db.flush()

        return plate

    def get_plate_by_code(self, plate_code: str) -> AddressPlate | None:
        return self.address_plate_repository.get_by_plate_code(plate_code)

    def verify_plate(self, plate_code: str) -> AddressPlate:
        plate = self.address_plate_repository.get_by_plate_code(
            plate_code
        )

        if plate is None:
            raise ValueError("Plate not found")

        if plate.status != "unactivated":
            raise ValueError("Plate cannot be verified in its current status")

        plate.status = "verified"
        plate.verified_at = datetime.now(UTC)

        self.db.flush()

        return plate
