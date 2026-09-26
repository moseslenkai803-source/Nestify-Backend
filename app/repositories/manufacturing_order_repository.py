from uuid import UUID

from sqlalchemy.orm import Session

from app.models.manufacturing_order import ManufacturingOrder


class ManufacturingOrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        order: ManufacturingOrder,
    ) -> ManufacturingOrder:
        self.db.add(order)
        self.db.flush()

        return order

    def get_by_id(
        self,
        order_id: UUID,
    ) -> ManufacturingOrder | None:
        return self.db.get(
            ManufacturingOrder,
            order_id,
        )

    def get_by_order_code(
        self,
        order_code: str,
    ) -> ManufacturingOrder | None:
        return (
            self.db.query(ManufacturingOrder)
            .filter(
                ManufacturingOrder.order_code == order_code,
            )
            .first()
        )

    def get_by_order_code_for_update(
        self,
        order_code: str,
    ) -> ManufacturingOrder | None:
        return (
            self.db.query(ManufacturingOrder)
            .filter(
                ManufacturingOrder.order_code == order_code,
            )
            .with_for_update()
            .first()
        )

    def get_by_status(
        self,
        status: str,
    ) -> list[ManufacturingOrder]:
        return (
            self.db.query(ManufacturingOrder)
            .filter(
                ManufacturingOrder.status == status,
            )
            .order_by(
                ManufacturingOrder.created_at.desc(),
            )
            .all()
        )
