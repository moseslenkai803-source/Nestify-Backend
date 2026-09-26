import uuid
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.user import User
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)


def create_employee(db_session):
    employee = User(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee


def create_plate(db_session):
    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    return plate


def record_event(service, plate_id, employee_id, event_type, notes=None):
    return service.record_event(
        plate_id=plate_id,
        event_type=event_type,
        performed_by=employee_id,
        notes=notes,
    )


def test_record_event_creates_manufactured_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    result = record_event(
        service,
        plate.id,
        employee.id,
        "manufactured",
        "Plate produced from manufacturing order",
    )

    assert isinstance(result, AddressPlateLifecycleEvent)
    assert result.plate_id == plate.id
    assert result.event_type == "manufactured"
    assert result.performed_by == employee.id
    assert result.notes == "Plate produced from manufacturing order"
    assert result.occurred_at is not None


@pytest.mark.parametrize("event_type", ["requested", "approved"])
def test_record_event_rejects_request_workflow_events(
    db_session,
    event_type,
):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle event type",
    ):
        record_event(
            service,
            plate.id,
            employee.id,
            event_type,
        )


def test_record_event_requires_existing_plate(db_session):
    employee = create_employee(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(ValueError, match="Plate not found"):
        record_event(
            service,
            uuid.uuid4(),
            employee.id,
            "manufactured",
        )


def test_record_event_rejects_unknown_event_type(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle event type",
    ):
        record_event(
            service,
            plate.id,
            employee.id,
            "unknown",
        )


def test_record_event_allows_complete_lifecycle(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    lifecycle = [
        "manufactured",
        "allocated",
        "dispatched",
        "installed",
        "verified",
        "activated",
    ]

    results = []

    for event_type in lifecycle:
        results.append(
            record_event(
                service,
                plate.id,
                employee.id,
                event_type,
            )
        )

    assert [event.event_type for event in results] == lifecycle


@pytest.mark.parametrize(
    ("valid_history", "invalid_next_event"),
    [
        (["manufactured"], "dispatched"),
        (["manufactured", "allocated"], "installed"),
        (
            ["manufactured", "allocated", "dispatched"],
            "verified",
        ),
        (
            [
                "manufactured",
                "allocated",
                "dispatched",
                "installed",
            ],
            "activated",
        ),
        (
            [
                "manufactured",
                "allocated",
                "dispatched",
                "installed",
                "verified",
            ],
            "installed",
        ),
    ],
)
def test_record_event_rejects_invalid_transitions(
    db_session,
    valid_history,
    invalid_next_event,
):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    for event_type in valid_history:
        record_event(
            service,
            plate.id,
            employee.id,
            event_type,
        )

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle transition",
    ):
        record_event(
            service,
            plate.id,
            employee.id,
            invalid_next_event,
        )


def test_record_event_rejects_non_manufactured_first_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle transition",
    ):
        record_event(
            service,
            plate.id,
            employee.id,
            "allocated",
        )


def test_record_event_rejects_duplicate_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    record_event(
        service,
        plate.id,
        employee.id,
        "manufactured",
    )

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle transition",
    ):
        record_event(
            service,
            plate.id,
            employee.id,
            "manufactured",
        )


def test_record_allocation_uses_lifecycle_validation(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    record_event(
        service,
        plate.id,
        employee.id,
        "manufactured",
    )

    result = service.record_allocation(
        plate_id=plate.id,
        performed_by=employee.id,
        notes="Allocated to property",
    )

    assert result.event_type == "allocated"
    assert result.notes == "Allocated to property"


def test_record_allocation_rejects_unmanufactured_plate(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle transition",
    ):
        service.record_allocation(
            plate_id=plate.id,
            performed_by=employee.id,
        )


def test_get_history_returns_lifecycle_events(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    record_event(
        service,
        plate.id,
        employee.id,
        "manufactured",
    )

    record_event(
        service,
        plate.id,
        employee.id,
        "allocated",
    )

    record_event(
        service,
        plate.id,
        employee.id,
        "dispatched",
    )

    history = service.get_history(plate.id)

    assert len(history) == 3
    assert [event.event_type for event in history] == [
        "manufactured",
        "allocated",
        "dispatched",
    ]


def test_get_latest_event_returns_latest_lifecycle_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    record_event(
        service,
        plate.id,
        employee.id,
        "manufactured",
    )

    record_event(
        service,
        plate.id,
        employee.id,
        "allocated",
    )

    result = service.get_latest_event(plate.id)

    assert result is not None
    assert result.event_type == "allocated"


def test_record_event_serializes_concurrent_lifecycle_transitions(
    db_session,
):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    setup_service = AddressPlateLifecycleService(db_session)

    record_event(
        setup_service,
        plate.id,
        employee.id,
        "manufactured",
    )

    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_locked = Event()
    second_started = Event()
    second_finished = Event()
    second_error = {}

    try:
        first_service = AddressPlateLifecycleService(first_session)

        result = record_event(
            first_service,
            plate.id,
            employee.id,
            "allocated",
        )

        assert result.event_type == "allocated"

        first_locked.set()

        def record_from_second_transaction():
            try:
                second_service = AddressPlateLifecycleService(
                    second_session
                )

                second_started.set()

                record_event(
                    second_service,
                    plate.id,
                    employee.id,
                    "allocated",
                )
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=record_from_second_transaction)
        thread.start()

        assert first_locked.is_set()
        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_session.commit()

        assert second_finished.wait(timeout=2)

        thread.join(timeout=2)

        assert isinstance(second_error.get("error"), ValueError)
        assert str(second_error["error"]) == (
            "Invalid lifecycle transition"
        )

    finally:
        if thread.is_alive():
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()
