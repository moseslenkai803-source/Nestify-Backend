import uuid
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal

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


def test_complete_manufacturing_order_rolls_back_partial_inventory_on_failure(
    db_session,
):
    from sqlalchemy.exc import IntegrityError
    import uuid

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

    invalid_completed_by = uuid.uuid4()

    try:
        with db_session.begin_nested():
            service.complete_order(
                order_code=order.order_code,
                completed_by=invalid_completed_by,
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError(
            "Manufacturing completion should fail when "
            "completed_by does not reference an existing user"
        )

    db_session.expire_all()

    persisted_order = (
        db_session.query(ManufacturingOrder)
        .filter(
            ManufacturingOrder.id == order.id,
        )
        .one()
    )

    assert persisted_order.status == "in_production"
    assert persisted_order.completed_at is None

    plates = (
        db_session.query(AddressPlate)
        .filter(
            AddressPlate.manufacturing_order_id == order.id,
        )
        .all()
    )

    assert plates == []


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


def test_complete_manufacturing_order_serializes_concurrent_completion_attempts(
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

    order_code = order.order_code
    employee_id = employee.id
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_locked = Event()
    second_started = Event()
    second_finished = Event()
    second_error = {}

    thread = None

    try:
        first_service = ManufacturingOrderService(first_session)

        locked_order = (
            first_service.manufacturing_order_repository
            .get_by_order_code_for_update(order_code)
        )

        assert locked_order is not None
        assert locked_order.status == "in_production"

        first_locked.set()

        def complete_from_second_transaction():
            try:
                second_service = ManufacturingOrderService(second_session)
                second_started.set()

                second_service.complete_order(
                    order_code=order_code,
                    completed_by=employee_id,
                )
            except Exception as exc:
                second_error['error'] = exc
            finally:
                second_finished.set()

        thread = Thread(target=complete_from_second_transaction)
        thread.start()

        assert first_locked.is_set()
        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_service.complete_order(
            order_code=order_code,
            completed_by=employee_id,
        )
        first_session.commit()

        assert second_finished.wait(timeout=2)

        thread.join(timeout=2)

        assert isinstance(second_error.get('error'), ValueError)
        assert str(second_error['error']) == (
            "Manufacturing order cannot be completed in its current status"
        )

        db_session.expire_all()

        plates = (
            db_session.query(AddressPlate)
            .filter(
                AddressPlate.manufacturing_order_id == order.id,
            )
            .all()
        )

        assert len(plates) == 2

    finally:
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()

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
