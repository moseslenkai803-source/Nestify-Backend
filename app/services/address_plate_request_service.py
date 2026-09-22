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

        existing_plate = (
            self.address_plate_repository.get_by_property_id(
                property_id
            )
        )

        if existing_plate is not None:
            if existing_plate.status == "active":
                raise ValueError(
                    "Property already has an active address plate"
                )

            raise ValueError(
                "Property already has an address plate"
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

    def approve_request(
        self,
        request_id: uuid.UUID,
    ) -> AddressPlateRequest:
        request = self.address_plate_request_repository.get_by_id(
            request_id
        )

        if request is None:
            raise ValueError("Address plate request not found")

        if request.status != "pending":
            raise ValueError("Address plate request is not pending")

        request.status = "approved"
        self.db.flush()

        return request

    def reject_request(
        self,
        request_id: uuid.UUID,
    ) -> AddressPlateRequest:
        request = self.address_plate_request_repository.get_by_id(
            request_id
        )

        if request is None:
            raise ValueError("Address plate request not found")

        if request.status != "pending":
            raise ValueError("Address plate request is not pending")

        request.status = "rejected"
        self.db.flush()

        return request
