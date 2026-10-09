import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AddressPlateRequestNotFoundError,
    PropertyAccessDeniedError,
)
from app.models.address_plate import AddressPlate
from app.models.user import User
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.address_plate_request_repository import (
    AddressPlateRequestRepository,
)
from app.repositories.property_repository import PropertyRepository
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.services.property_access_service import PropertyAccessService


class AddressPlateAllocationService:
    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)
        self.address_plate_request_repository = (
            AddressPlateRequestRepository(db)
        )
        self.property_repository = PropertyRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)
        self.property_access_service = PropertyAccessService(db)

    def allocate_plate(
        self,
        request_id: uuid.UUID,
        user: User,
    ) -> AddressPlate:
        request = self.address_plate_request_repository.get_by_id(
            request_id
        )

        if request is None:
            raise AddressPlateRequestNotFoundError(
                "Address plate request not found"
            )

        try:
            self.property_access_service.authorize(
                user_id=user.id,
                property_id=request.property_id,
                access_type="plate_operations",
            )
        except ValueError as exc:
            raise PropertyAccessDeniedError(str(exc)) from exc

        if request.status != "approved":
            raise ValueError(
                "Address plate request is not approved"
            )

        property = self.property_repository.get_by_id_for_update(
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
            performed_by=user.id,
        )

        request.status = "fulfilled"

        self.db.flush()

        return plate
