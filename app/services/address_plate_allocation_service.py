import uuid

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.models.address_plate_request import AddressPlateRequest
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.address_plate_request_repository import (
    AddressPlateRequestRepository,
)
from app.repositories.property_repository import PropertyRepository
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)


class AddressPlateAllocationService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)
        self.address_plate_request_repository = (
            AddressPlateRequestRepository(db)
        )
        self.property_repository = PropertyRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)

    def allocate_plate(
        self,
        request_id: uuid.UUID,
        performed_by: uuid.UUID,
    ) -> AddressPlate:
        request = self.address_plate_request_repository.get_by_id(
            request_id
        )

        if request is None:
            raise ValueError("Address plate request not found")

        if request.status != "approved":
            raise ValueError(
                "Address plate request is not approved"
            )

        property = self.property_repository.get_by_id(
            request.property_id
        )

        if property is None:
            raise ValueError("Property not found")

        existing_plate = (
            self.address_plate_repository.get_by_property_id(
                property.id
            )
        )

        if existing_plate is not None:
            raise ValueError(
                "Property already has an address plate"
            )

        plate = (
            self.address_plate_repository
            .get_next_manufactured_plate_for_update()
        )

        if plate is None:
            raise ValueError("No address plates available for allocation")

        plate.property_id = property.id

        self.lifecycle_service.record_allocation(
            plate_id=plate.id,
            performed_by=performed_by,
        )

        request.status = "fulfilled"

        self.db.flush()

        return plate
