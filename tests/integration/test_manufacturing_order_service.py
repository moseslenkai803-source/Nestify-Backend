import uuid

import pytest

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.manufacturing_order import ManufacturingOrder
from app.models.user import User
from app.services.manufacturing_order_service import (
    ManufacturingOrderService,
)


def create_employee(db_session):
    employee = User(
        email=f"manufacturing-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )
    db_session.add(employee)
    db_session.flush()

    return employee


def test_create_manufacturing_order(db_session):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    result = service.create_order(
        quantity=10,
        created_by=employee.id,
    )

    assert isinstance(result, ManufacturingOrder)
    assert result.id is not None
    assert result.order_code.startswith("MO-")
    assert result.quantity == 10
    assert result.status == "draft"
    assert result.created_by == employee.id
    assert result.approved_by is None
    assert result.started_at is None
    assert result.completed_at is None
    assert result.created_at is not None
    assert result.updated_at is not None


def test_create_manufacturing_order_rejects_zero_quantity(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    with pytest.raises(
        ValueError,
        match="Manufacturing quantity must be greater than zero",
    ):
        service.create_order(
            quantity=0,
            created_by=employee.id,
        )


def test_create_manufacturing_order_rejects_negative_quantity(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    with pytest.raises(
        ValueError,
        match="Manufacturing quantity must be greater than zero",
    ):
        service.create_order(
            quantity=-5,
            created_by=employee.id,
        )


def test_create_manufacturing_orders_generate_unique_codes(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    first_order = service.create_order(
        quantity=5,
        created_by=employee.id,
    )

    second_order = service.create_order(
        quantity=5,
        created_by=employee.id,
    )

    assert first_order.order_code != second_order.order_code


def test_approve_manufacturing_order(db_session):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=10,
        created_by=employee.id,
    )

    result = service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    assert result.status == "approved"
    assert result.approved_by == employee.id


def test_approve_manufacturing_order_rejects_missing_order(
    db_session,
):
    service = ManufacturingOrderService(db_session)

    with pytest.raises(
        ValueError,
        match="Manufacturing order not found",
    ):
        service.approve_order(
            order_code="MO-NOTFOUND",
            approved_by=uuid.uuid4(),
        )


def test_approve_manufacturing_order_rejects_non_draft_order(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=10,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Manufacturing order cannot be approved in its current status",
    ):
        service.approve_order(
            order_code=order.order_code,
            approved_by=employee.id,
        )


def test_start_manufacturing_order(db_session):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=10,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    result = service.start_order(
        order_code=order.order_code,
    )

    assert result.status == "in_production"
    assert result.started_at is not None


def test_start_manufacturing_order_rejects_missing_order(
    db_session,
):
    service = ManufacturingOrderService(db_session)

    with pytest.raises(
        ValueError,
        match="Manufacturing order not found",
    ):
        service.start_order(
            order_code="MO-NOTFOUND",
        )


def test_start_manufacturing_order_rejects_non_approved_order(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=10,
        created_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Manufacturing order cannot be started in its current status",
    ):
        service.start_order(
            order_code=order.order_code,
        )


def test_complete_manufacturing_order_creates_plate_inventory(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=3,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    service.start_order(
        order_code=order.order_code,
    )

    result = service.complete_order(
        order_code=order.order_code,
        completed_by=employee.id,
    )

    assert result.status == "completed"
    assert result.completed_at is not None

    plates = (
        db_session.query(AddressPlate)
        .filter(
            AddressPlate.manufacturing_order_id == order.id,
        )
        .all()
    )

    assert len(plates) == 3

    for plate in plates:
        assert plate.manufacturing_order_id == order.id
        assert plate.plate_code.startswith("PLATE-")
        assert plate.status == "unactivated"
        assert plate.property_id is None

        events = (
            db_session.query(AddressPlateLifecycleEvent)
            .filter(
                AddressPlateLifecycleEvent.plate_id == plate.id,
            )
            .all()
        )

        assert len(events) == 1
        assert events[0].event_type == "manufactured"
        assert events[0].performed_by == employee.id


def test_complete_manufacturing_order_rejects_non_production_order(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=3,
        created_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Manufacturing order cannot be completed in its current status",
    ):
        service.complete_order(
            order_code=order.order_code,
            completed_by=employee.id,
        )


def test_complete_manufacturing_order_cannot_be_completed_twice(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    service.start_order(
        order_code=order.order_code,
    )

    service.complete_order(
        order_code=order.order_code,
        completed_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Manufacturing order cannot be completed in its current status",
    ):
        service.complete_order(
            order_code=order.order_code,
            completed_by=employee.id,
        )

    plates = (
        db_session.query(AddressPlate)
        .filter(
            AddressPlate.manufacturing_order_id == order.id,
        )
        .all()
    )

    assert len(plates) == 2


def test_cancel_manufacturing_order_from_draft(db_session):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    result = service.cancel_order(
        order_code=order.order_code,
    )

    assert result.status == "cancelled"


def test_cancel_manufacturing_order_from_approved(db_session):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    result = service.cancel_order(
        order_code=order.order_code,
    )

    assert result.status == "cancelled"


def test_cancel_manufacturing_order_from_in_production(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    service.start_order(
        order_code=order.order_code,
    )

    result = service.cancel_order(
        order_code=order.order_code,
    )

    assert result.status == "cancelled"


def test_cancel_completed_manufacturing_order_is_rejected(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    service.start_order(
        order_code=order.order_code,
    )

    service.complete_order(
        order_code=order.order_code,
        completed_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Manufacturing order cannot be cancelled in its current status",
    ):
        service.cancel_order(
            order_code=order.order_code,
        )


def test_cancelled_manufacturing_order_cannot_be_cancelled_again(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    service.cancel_order(
        order_code=order.order_code,
    )

    with pytest.raises(
        ValueError,
        match="Manufacturing order cannot be cancelled in its current status",
    ):
        service.cancel_order(
            order_code=order.order_code,
        )


def test_get_manufacturing_order_plates(
    db_session,
):
    employee = create_employee(db_session)

    service = ManufacturingOrderService(db_session)

    order = service.create_order(
        quantity=2,
        created_by=employee.id,
    )

    service.approve_order(
        order_code=order.order_code,
        approved_by=employee.id,
    )

    service.start_order(
        order_code=order.order_code,
    )

    service.complete_order(
        order_code=order.order_code,
        completed_by=employee.id,
    )

    result = service.get_order_plates(
        order_code=order.order_code,
    )

    assert len(result) == 2
    assert all(isinstance(plate, AddressPlate) for plate in result)
    assert all(
        plate.manufacturing_order_id == order.id
        for plate in result
    )


def test_get_manufacturing_order_plates_rejects_missing_order(
    db_session,
):
    service = ManufacturingOrderService(db_session)

    with pytest.raises(
        ValueError,
        match="Manufacturing order not found",
    ):
        service.get_order_plates(
            order_code="MO-NOTFOUND",
        )
