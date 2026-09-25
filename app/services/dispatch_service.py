import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.dispatch import Dispatch
from app.models.dispatch_item import DispatchItem
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.dispatch_item_repository import DispatchItemRepository
from app.repositories.dispatch_repository import DispatchRepository
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)


class DispatchService:
    VALID_STATUSES = {
        "draft",
        "ready",
        "dispatched",
        "delivered",
        "cancelled",
    }

    ALLOWED_TRANSITIONS = {
        "draft": {"ready", "cancelled"},
        "ready": {"dispatched", "cancelled"},
        "dispatched": {"delivered"},
        "delivered": set(),
        "cancelled": set(),
    }

    def __init__(self, db: Session):
        self.db = db
        self.dispatch_repository = DispatchRepository(db)
        self.dispatch_item_repository = DispatchItemRepository(db)
        self.address_plate_repository = AddressPlateRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)

    def create_dispatch(
        self,
        plate_ids: list[uuid.UUID],
        destination: str,
        recipient_name: str,
        recipient_phone: str,
        created_by: uuid.UUID,
        tracking_reference: str | None = None,
    ) -> Dispatch:
        if not plate_ids:
            raise ValueError("Dispatch must contain at least one plate")

        if len(set(plate_ids)) != len(plate_ids):
            raise ValueError("Dispatch cannot contain duplicate plates")

        for plate_id in plate_ids:
            plate = self.address_plate_repository.get_by_id(plate_id)

            if plate is None:
                raise ValueError("Address plate not found")

            if plate.property_id is None:
                raise ValueError(
                    "Address plate must be allocated to a property before dispatch"
                )

            latest_event = self.lifecycle_service.get_latest_event(
                plate_id
            )

            if latest_event is None:
                raise ValueError(
                    "Address plate must be manufactured before dispatch"
                )

            if latest_event.event_type != "allocated":
                raise ValueError(
                    "Address plate is not ready for dispatch"
                )

            existing_item = (
                self.dispatch_item_repository.get_by_plate_id(
                    plate_id
                )
            )

            if existing_item is not None:
                raise ValueError(
                    "Address plate is already assigned to a dispatch"
                )

        dispatch = Dispatch(
            dispatch_code=f"DSP-{uuid.uuid4().hex[:12].upper()}",
            status="draft",
            destination=destination,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            tracking_reference=tracking_reference,
            created_by=created_by,
        )

        self.dispatch_repository.add(dispatch)

        for plate_id in plate_ids:
            item = DispatchItem(
                dispatch_id=dispatch.id,
                plate_id=plate_id,
            )

            self.dispatch_item_repository.add(item)

        return dispatch

    def get_dispatch(
        self,
        dispatch_code: str,
    ) -> Dispatch:
        dispatch = self.dispatch_repository.get_by_dispatch_code(
            dispatch_code
        )

        if dispatch is None:
            raise ValueError("Dispatch not found")

        return dispatch

    def get_dispatch_plates(
        self,
        dispatch_code: str,
    ) -> list[DispatchItem]:
        dispatch = self.get_dispatch(dispatch_code)

        return self.dispatch_item_repository.get_by_dispatch_id(
            dispatch.id
        )

    def mark_ready(
        self,
        dispatch_code: str,
    ) -> Dispatch:
        dispatch = self.get_dispatch(dispatch_code)

        self._validate_transition(
            dispatch,
            "ready",
        )

        items = self.dispatch_item_repository.get_by_dispatch_id(
            dispatch.id
        )

        if not items:
            raise ValueError(
                "Dispatch must contain at least one plate"
            )

        dispatch.status = "ready"
        self.db.flush()

        return dispatch

    def mark_dispatched(
        self,
        dispatch_code: str,
        performed_by: uuid.UUID,
    ) -> Dispatch:
        dispatch = self.get_dispatch(dispatch_code)

        self._validate_transition(
            dispatch,
            "dispatched",
        )

        items = self.dispatch_item_repository.get_by_dispatch_id(
            dispatch.id
        )

        if not items:
            raise ValueError(
                "Dispatch must contain at least one plate"
            )

        for item in items:
            latest_event = self.lifecycle_service.get_latest_event(
                item.plate_id
            )

            if latest_event is None:
                raise ValueError(
                    "Address plate has no lifecycle history"
                )

            if latest_event.event_type != "allocated":
                raise ValueError(
                    "Address plate is not ready for dispatch"
                )

        dispatch.status = "dispatched"

        for item in items:
            self.lifecycle_service.record_event(
                plate_id=item.plate_id,
                event_type="dispatched",
                performed_by=performed_by,
                notes=f"Dispatched with {dispatch.dispatch_code}",
            )

        self.db.flush()

        return dispatch

    def mark_delivered(
        self,
        dispatch_code: str,
    ) -> Dispatch:
        dispatch = self.get_dispatch(dispatch_code)

        self._validate_transition(
            dispatch,
            "delivered",
        )

        dispatch.status = "delivered"
        self.db.flush()

        return dispatch

    def cancel_dispatch(
        self,
        dispatch_code: str,
    ) -> Dispatch:
        dispatch = self.get_dispatch(dispatch_code)

        self._validate_transition(
            dispatch,
            "cancelled",
        )

        items = self.dispatch_item_repository.get_by_dispatch_id(
            dispatch.id
        )

        if not items:
            raise ValueError(
                "Dispatch must contain at least one plate"
            )

        dispatch.status = "cancelled"

        for item in items:
            item.released_at = datetime.now(UTC)

        self.db.flush()

        return dispatch

    def _validate_transition(
        self,
        dispatch: Dispatch,
        target_status: str,
    ) -> None:
        if target_status not in self.VALID_STATUSES:
            raise ValueError("Invalid dispatch status")

        allowed_targets = self.ALLOWED_TRANSITIONS.get(
            dispatch.status,
            set(),
        )

        if target_status not in allowed_targets:
            raise ValueError(
                "Dispatch cannot transition to the requested status"
            )
