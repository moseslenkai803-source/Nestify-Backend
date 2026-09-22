import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.address_plate_request import AddressPlateRequest
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.address_plate_request_repository import (
    AddressPlateRequestRepository,
)
from app.repositories.property_repository import PropertyRepository


class AddressPlateRequestService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repository = PropertyRepository(db)
        self.address_plate_repository = AddressPlateRepository(db)
        self.address_plate_request_repository = (
            AddressPlateRequestRepository(db)
        )

    def create_request(
        self,
        property_id: uuid.UUID,
        requested_by: uuid.UUID,
    ) -> AddressPlateRequest:
        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        active_plate = (
            self.address_plate_repository.get_active_by_property_id(
                property_id
            )
        )

        if active_plate is not None:
            raise ValueError(
                "Property already has an active address plate"
            )

        pending_request = (
            self.address_plate_request_repository.get_pending_by_property_id(
                property_id
            )
        )

        if pending_request is not None:
            raise ValueError(
                "Property already has a pending address plate request"
            )

        request = AddressPlateRequest(
            property_id=property_id,
            requested_by=requested_by,
            status="pending",
            requested_at=datetime.now(UTC),
        )

        return self.address_plate_request_repository.add(request)
