from sqlalchemy.orm import Session

from app.repositories.address_plate_repository import AddressPlateRepository


class PlateInventoryQueryService:
    def __init__(self, db: Session):
        self.address_plate_repository = AddressPlateRepository(db)

    def list_inventory(self) -> list[dict]:
        records = self.address_plate_repository.get_inventory_records()

        return [
            {
                "id": plate.id,
                "plate_code": plate.plate_code,
                "property_id": plate.property_id,
                "property_code": property_code,
                "property_name": property_name,
                "status": plate.status,
                "lifecycle_status": lifecycle_status,
                "activated_at": plate.activated_at,
            }
            for plate, property_code, property_name, lifecycle_status in records
        ]
