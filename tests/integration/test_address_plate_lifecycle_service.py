import uuid

import pytest

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


def test_record_event_creates_requested_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    result = service.record_event(
        plate_id=plate.id,
        event_type="requested",
        performed_by=employee.id,
        notes="Plate requested",
    )

    assert isinstance(result, AddressPlateLifecycleEvent)
    assert result.plate_id == plate.id
    assert result.event_type == "requested"
    assert result.performed_by == employee.id
    assert result.notes == "Plate requested"
    assert result.occurred_at is not None


def test_record_event_requires_existing_plate(db_session):
    employee = create_employee(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(ValueError, match="Plate not found"):
        service.record_event(
            plate_id=uuid.uuid4(),
            event_type="requested",
            performed_by=employee.id,
        )


def test_record_event_rejects_unknown_event_type(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle event type",
    ):
        service.record_event(
            plate_id=plate.id,
            event_type="unknown",
            performed_by=employee.id,
        )


def test_record_event_requires_correct_transition(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    service.record_event(
        plate_id=plate.id,
        event_type="requested",
        performed_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Invalid lifecycle transition",
    ):
        service.record_event(
            plate_id=plate.id,
            event_type="manufactured",
            performed_by=employee.id,
        )


def test_record_event_allows_next_valid_transition(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    service.record_event(
        plate_id=plate.id,
        event_type="requested",
        performed_by=employee.id,
    )

    result = service.record_event(
        plate_id=plate.id,
        event_type="approved",
        performed_by=employee.id,
    )

    assert result.event_type == "approved"


def test_get_history_returns_lifecycle_events(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    service.record_event(
        plate_id=plate.id,
        event_type="requested",
        performed_by=employee.id,
    )

    service.record_event(
        plate_id=plate.id,
        event_type="approved",
        performed_by=employee.id,
    )

    history = service.get_history(plate.id)

    assert len(history) == 2
    assert history[0].event_type == "requested"
    assert history[1].event_type == "approved"


def test_get_latest_event_returns_latest_lifecycle_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)

    service = AddressPlateLifecycleService(db_session)

    service.record_event(
        plate_id=plate.id,
        event_type="requested",
        performed_by=employee.id,
    )

    service.record_event(
        plate_id=plate.id,
        event_type="approved",
        performed_by=employee.id,
    )

    result = service.get_latest_event(plate.id)

    assert result is not None
    assert result.event_type == "approved"

def test_record_event_allows_manufactured_as_first_event(db_session):
    employee = create_employee(db_session)
    plate = create_plate(db_session)
    service = AddressPlateLifecycleService(db_session)

    result = service.record_event(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=employee.id,
        notes="Plate produced from manufacturing order",
    )

    assert isinstance(result, AddressPlateLifecycleEvent)
    assert result.plate_id == plate.id
    assert result.event_type == "manufactured"
    assert result.performed_by == employee.id
    assert result.notes == "Plate produced from manufacturing order"
    assert result.occurred_at is not None
