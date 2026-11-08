import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.address_plate import AddressPlate
from app.models.manufacturing_order import ManufacturingOrder
from app.repositories.address_plate_repository import (
    AddressPlateRepository,
)
from app.repositories.manufacturing_order_repository import (
    ManufacturingOrderRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.services.plate_inventory_service import PlateInventoryService


class ManufacturingOrderService:
    VALID_STATUSES = {
        "draft",
        "approved",
        "in_production",
        "completed",
        "cancelled",
    }

    def __init__(self, db: Session):
        self.db = db
        self.manufacturing_order_repository = (
            ManufacturingOrderRepository(db)
        )
        self.user_repository = UserRepository(db)
        self.address_plate_repository = AddressPlateRepository(db)
        self.plate_inventory_service = PlateInventoryService(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)

    def start_order(
        self,
        order_code: str,
    ) -> ManufacturingOrder:
        order = self.manufacturing_order_repository.get_by_order_code_for_update(
            order_code
        )

        if order is None:
            raise ValueError("Manufacturing order not found")

        if order.status != "approved":
            raise ValueError(
                "Manufacturing order cannot be started in its current status"
            )

        order.status = "in_production"
        order.started_at = datetime.now(UTC)

        self.db.flush()

        return order

    def approve_order(
        self,
        order_code: str,
        approved_by: uuid.UUID,
    ) -> ManufacturingOrder:
        order = self.manufacturing_order_repository.get_by_order_code_for_update(
            order_code
        )

        if order is None:
            raise ValueError("Manufacturing order not found")

        if order.status != "draft":
            raise ValueError(
                "Manufacturing order cannot be approved in its current status"
            )

        order.status = "approved"
        order.approved_by = approved_by

        self.db.flush()

        return order

    def complete_order(
        self,
        order_code: str,
        completed_by: uuid.UUID,
    ) -> ManufacturingOrder:
        order = self.manufacturing_order_repository.get_by_order_code_for_update(
            order_code
        )

        if order is None:
            raise ValueError("Manufacturing order not found")

        if order.status != "in_production":
            raise ValueError(
                "Manufacturing order cannot be completed in its current status"
            )

        for _ in range(order.quantity):
            plate = self.plate_inventory_service.create_plate(
                manufacturing_order_id=order.id,
            )

            self.lifecycle_service.record_event(
                plate_id=plate.id,
                event_type="manufactured",
                performed_by=completed_by,
                notes=f"Manufactured as part of order {order.order_code}",
            )

        order.status = "completed"
        order.completed_at = datetime.now(UTC)

        self.db.flush()

        return order

    def list_orders(
        self,
        status: str | None = None,
    ) -> list[ManufacturingOrder]:
        if status is not None and status not in self.VALID_STATUSES:
            raise ValueError("Invalid manufacturing order status")

        if status is not None:
            return self.manufacturing_order_repository.get_by_status(status)

        orders = []
        for order_status in self.VALID_STATUSES:
            orders.extend(
                self.manufacturing_order_repository.get_by_status(
                    order_status
                )
            )

        return sorted(
            orders,
            key=lambda order: order.created_at,
            reverse=True,
        )

    def get_order(
        self,
        order_code: str,
    ) -> ManufacturingOrder:
        order = self.manufacturing_order_repository.get_by_order_code(
            order_code
        )

        if order is None:
            raise ValueError("Manufacturing order not found")

        return order

    def get_order_plates(
        self,
        order_code: str,
    ) -> list[AddressPlate]:
        order = self.manufacturing_order_repository.get_by_order_code(
            order_code
        )

        if order is None:
            raise ValueError("Manufacturing order not found")

        return self.address_plate_repository.get_by_manufacturing_order_id(
            order.id
        )

    def cancel_order(
        self,
        order_code: str,
        cancelled_by: uuid.UUID,
        reason: str,
    ) -> ManufacturingOrder:
        order = self.manufacturing_order_repository.get_by_order_code_for_update(
            order_code
        )

        if order is None:
            raise ValueError("Manufacturing order not found")

        if order.status not in {
            "draft",
            "approved",
            "in_production",
        }:
            raise ValueError(
                "Manufacturing order cannot be cancelled in its current status"
            )

        cancelling_user = self.user_repository.get_by_id(cancelled_by)

        if cancelling_user is None:
            raise ValueError("Cancelling employee not found")

        if not cancelling_user.is_active:
            raise ValueError("Cancelling employee is inactive")

        if cancelling_user.role not in {"admin", "employee"}:
            raise ValueError(
                "Only Nestify employees can cancel manufacturing orders"
            )

        reason = reason.strip()
        if not reason:
            raise ValueError("Cancellation reason is required")

        if len(reason) > 2000:
            raise ValueError(
                "Cancellation reason must not exceed 2000 characters"
            )

        order.status = "cancelled"
        order.cancelled_by = cancelled_by
        order.cancelled_at = datetime.now(UTC)
        order.cancellation_reason = reason

        self.db.flush()

        return order

    def create_order(
        self,
        quantity: int,
        created_by: uuid.UUID,
    ) -> ManufacturingOrder:
        if quantity <= 0:
            raise ValueError(
                "Manufacturing quantity must be greater than zero"
            )

        order_code = (
            f"MO-{uuid.uuid4().hex[:12].upper()}"
        )

        order = ManufacturingOrder(
            order_code=order_code,
            quantity=quantity,
            status="draft",
            created_by=created_by,
        )

        self.manufacturing_order_repository.add(order)

        return order
