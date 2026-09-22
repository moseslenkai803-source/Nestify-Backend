from uuid import UUID

from sqlalchemy.orm import Session

from app.models.dispatch_item import DispatchItem


class DispatchItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        item: DispatchItem,
    ) -> DispatchItem:
        self.db.add(item)
        self.db.flush()

        return item

    def get_by_id(
        self,
        item_id: UUID,
    ) -> DispatchItem | None:
        return self.db.get(
            DispatchItem,
            item_id,
        )

    def get_by_dispatch_id(
        self,
        dispatch_id: UUID,
    ) -> list[DispatchItem]:
        return (
            self.db.query(DispatchItem)
            .filter(
                DispatchItem.dispatch_id == dispatch_id,
            )
            .order_by(
                DispatchItem.created_at.asc(),
            )
            .all()
        )

    def get_by_plate_id(
        self,
        plate_id: UUID,
    ) -> DispatchItem | None:
        return (
            self.db.query(DispatchItem)
            .filter(
                DispatchItem.plate_id == plate_id,
                DispatchItem.released_at.is_(None),
            )
            .first()
        )
