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
