import uuid

from sqlalchemy.orm import Session

from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)


class AddressPlateLifecycleEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        event: AddressPlateLifecycleEvent,
    ) -> AddressPlateLifecycleEvent:
        self.db.add(event)
        self.db.flush()

        return event

    def get_by_plate_id(
        self,
        plate_id: uuid.UUID,
    ) -> list[AddressPlateLifecycleEvent]:
        return (
            self.db.query(AddressPlateLifecycleEvent)
            .filter(
                AddressPlateLifecycleEvent.plate_id == plate_id,
            )
            .order_by(
                AddressPlateLifecycleEvent.occurred_at.asc(),
                AddressPlateLifecycleEvent.id.asc(),
            )
            .all()
        )

    def get_latest_by_plate_id(
        self,
        plate_id: uuid.UUID,
    ) -> AddressPlateLifecycleEvent | None:
        return (
            self.db.query(AddressPlateLifecycleEvent)
            .filter(
                AddressPlateLifecycleEvent.plate_id == plate_id,
            )
            .order_by(
                AddressPlateLifecycleEvent.occurred_at.desc(),
                AddressPlateLifecycleEvent.id.desc(),
            )
            .first()
        )
