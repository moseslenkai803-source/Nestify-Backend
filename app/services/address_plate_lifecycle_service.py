import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.repositories.address_plate_lifecycle_event_repository import (
    AddressPlateLifecycleEventRepository,
)
from app.repositories.address_plate_repository import AddressPlateRepository


class AddressPlateLifecycleService:
    LIFECYCLE_TRANSITIONS = {
        "manufactured": "allocated",
        "allocated": "dispatched",
        "dispatched": "installed",
        "installed": "verified",
        "verified": "activated",
    }

    VALID_EVENT_TYPES = set(LIFECYCLE_TRANSITIONS) | {"activated"}

    def __init__(self, db: Session):
        self.db = db
        self.address_plate_repository = AddressPlateRepository(db)
        self.lifecycle_event_repository = (
            AddressPlateLifecycleEventRepository(db)
        )

    def record_event(
        self,
        plate_id: uuid.UUID,
        event_type: str,
        performed_by: uuid.UUID,
        notes: str | None = None,
    ) -> AddressPlateLifecycleEvent:
        if event_type == "activated":
            raise ValueError(
                "Plate activation must use activate_plate"
            )

        plate = self.address_plate_repository.get_by_id_for_update(plate_id)

        if plate is None:
            raise ValueError("Plate not found")

        return self._record_event(
            plate=plate,
            event_type=event_type,
            performed_by=performed_by,
            notes=notes,
        )

    def _record_event(
        self,
        plate: AddressPlate,
        event_type: str,
        performed_by: uuid.UUID,
        notes: str | None = None,
    ) -> AddressPlateLifecycleEvent:
        if event_type not in self.VALID_EVENT_TYPES:
            raise ValueError("Invalid lifecycle event type")

        latest_event = (
            self.lifecycle_event_repository.get_latest_by_plate_id(
                plate.id
            )
        )

        if latest_event is None:
            if event_type != "manufactured":
                raise ValueError("Invalid lifecycle transition")
        else:
            expected_event = self.LIFECYCLE_TRANSITIONS.get(
                latest_event.event_type
            )

            if event_type != expected_event:
                raise ValueError("Invalid lifecycle transition")

        event = AddressPlateLifecycleEvent(
            plate_id=plate.id,
            event_type=event_type,
            performed_by=performed_by,
            notes=notes,
        )

        self.lifecycle_event_repository.add(event)

        return event

    def activate_plate(
        self,
        plate_id: uuid.UUID,
        performed_by: uuid.UUID,
        notes: str | None = None,
    ) -> AddressPlate:
        plate = self.address_plate_repository.get_by_id_for_update(plate_id)

        if plate is None:
            raise ValueError("Plate not found")

        if plate.status == "active":
            raise ValueError("Plate is already active")

        latest_event = (
            self.lifecycle_event_repository.get_latest_by_plate_id(
                plate_id
            )
        )

        if latest_event is None or latest_event.event_type != "verified":
            raise ValueError(
                "Only verified plates can be activated"
            )

        plate.status = "active"
        plate.activated_at = datetime.now(UTC)

        self._record_event(
            plate=plate,
            event_type="activated",
            performed_by=performed_by,
            notes=notes,
        )

        self.db.flush()

        return plate

    def record_allocation(
        self,
        plate_id: uuid.UUID,
        performed_by: uuid.UUID,
        notes: str | None = None,
    ) -> AddressPlateLifecycleEvent:
        return self.record_event(
            plate_id=plate_id,
            event_type="allocated",
            performed_by=performed_by,
            notes=notes,
        )

    def get_history(
        self,
        plate_id: uuid.UUID,
    ) -> list[AddressPlateLifecycleEvent]:
        plate = self.address_plate_repository.get_by_id(plate_id)

        if plate is None:
            raise ValueError("Plate not found")

        return self.lifecycle_event_repository.get_by_plate_id(
            plate_id
        )

    def get_latest_event(
        self,
        plate_id: uuid.UUID,
    ) -> AddressPlateLifecycleEvent | None:
        plate = self.address_plate_repository.get_by_id(plate_id)

        if plate is None:
            raise ValueError("Plate not found")

        return self.lifecycle_event_repository.get_latest_by_plate_id(
            plate_id
        )
