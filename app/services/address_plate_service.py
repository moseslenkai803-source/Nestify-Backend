from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.repositories.address_plate_repository import AddressPlateRepository


class AddressPlateService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)

    def get_plate_by_code(self, plate_code: str) -> AddressPlate | None:
        return self.address_plate_repository.get_by_plate_code(
            plate_code
        )
