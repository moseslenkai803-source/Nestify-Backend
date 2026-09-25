import uuid

import pytest

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.dispatch_item import DispatchItem
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.dispatch_service import DispatchService


def create_employee(db_session):
    employee = User(
        email=f"dispatch-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee


def create_landlord_and_property(db_session):
    user = User(
        email=f"dispatch-landlord-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )

    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Dispatch Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )

    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Dispatch Test Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(property)
    db_session.flush()

    return user, property


def create_manufactured_allocated_plate(
    db_session,
    property_id,
    employee_id,
):
    plate = AddressPlate(
        property_id=property_id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    event = AddressPlateLifecycleEvent(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=employee_id,
        notes="Manufactured for dispatch test",
    )
    db_session.add(event)
    db_session.flush()

    allocation_event = AddressPlateLifecycleEvent(
        plate_id=plate.id,
        event_type="allocated",
        performed_by=employee_id,
        notes="Allocated for dispatch test",
    )
    db_session.add(allocation_event)
    db_session.flush()

    return plate


def test_create_dispatch(db_session):
    employee = create_employee(db_session)
    _, first_property = create_landlord_and_property(db_session)
    _, second_property = create_landlord_and_property(db_session)

    first_plate = create_manufactured_allocated_plate(
        db_session,
        first_property.id,
        employee.id,
    )

    second_plate = create_manufactured_allocated_plate(
        db_session,
        second_property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    result = service.create_dispatch(
        plate_ids=[first_plate.id, second_plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
        tracking_reference="TRACK-001",
    )

    assert result.id is not None
    assert result.dispatch_code.startswith("DSP-")
    assert result.status == "draft"
    assert result.destination == "Nairobi"
    assert result.recipient_name == "Jane Doe"
    assert result.recipient_phone == "+254711111111"
    assert result.tracking_reference == "TRACK-001"
    assert result.created_by == employee.id

    items = (
        db_session.query(DispatchItem)
        .filter(
            DispatchItem.dispatch_id == result.id,
        )
        .all()
    )

    assert len(items) == 2
    assert {item.plate_id for item in items} == {
        first_plate.id,
        second_plate.id,
    }

    events = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id.in_(
                [first_plate.id, second_plate.id]
            ),
        )
        .all()
    )

    assert len(events) == 4
    assert {e.event_type for e in events} == {"manufactured", "allocated"}


def test_create_dispatch_rejects_empty_plate_list(db_session):
    employee = create_employee(db_session)

    service = DispatchService(db_session)

    with pytest.raises(
        ValueError,
        match="Dispatch must contain at least one plate",
    ):
        service.create_dispatch(
            plate_ids=[],
            destination="Nairobi",
            recipient_name="Jane Doe",
            recipient_phone="+254711111111",
            created_by=employee.id,
        )


def test_create_dispatch_rejects_duplicate_plate_ids(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    with pytest.raises(
        ValueError,
        match="Dispatch cannot contain duplicate plates",
    ):
        service.create_dispatch(
            plate_ids=[plate.id, plate.id],
            destination="Nairobi",
            recipient_name="Jane Doe",
            recipient_phone="+254711111111",
            created_by=employee.id,
        )


def test_create_dispatch_rejects_missing_plate(db_session):
    employee = create_employee(db_session)

    service = DispatchService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate not found",
    ):
        service.create_dispatch(
            plate_ids=[uuid.uuid4()],
            destination="Nairobi",
            recipient_name="Jane Doe",
            recipient_phone="+254711111111",
            created_by=employee.id,
        )


def test_create_dispatch_rejects_unallocated_plate(db_session):
    employee = create_employee(db_session)

    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    db_session.add(
        AddressPlateLifecycleEvent(
            plate_id=plate.id,
            event_type="manufactured",
            performed_by=employee.id,
        )
    )
    db_session.flush()

    service = DispatchService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate must be allocated to a property before dispatch",
    ):
        service.create_dispatch(
            plate_ids=[plate.id],
            destination="Nairobi",
            recipient_name="Jane Doe",
            recipient_phone="+254711111111",
            created_by=employee.id,
        )


def test_create_dispatch_rejects_unmanufactured_plate(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    service = DispatchService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate must be manufactured before dispatch",
    ):
        service.create_dispatch(
            plate_ids=[plate.id],
            destination="Nairobi",
            recipient_name="Jane Doe",
            recipient_phone="+254711111111",
            created_by=employee.id,
        )


def test_create_dispatch_rejects_plate_already_in_dispatch(
    db_session,
):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    first_dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    assert first_dispatch.status == "draft"

    with pytest.raises(
        ValueError,
        match="Address plate is already assigned to a dispatch",
    ):
        service.create_dispatch(
            plate_ids=[plate.id],
            destination="Nairobi",
            recipient_name="Jane Doe",
            recipient_phone="+254711111111",
            created_by=employee.id,
        )


def test_mark_dispatch_ready(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    result = service.mark_ready(dispatch.dispatch_code)

    assert result.status == "ready"


def test_mark_ready_rejects_non_draft_dispatch(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.mark_ready(dispatch.dispatch_code)

    with pytest.raises(
        ValueError,
        match="Dispatch cannot transition to the requested status",
    ):
        service.mark_ready(dispatch.dispatch_code)


def test_mark_dispatched_records_lifecycle_events(db_session):
    employee = create_employee(db_session)
    _, first_property = create_landlord_and_property(db_session)
    _, second_property = create_landlord_and_property(db_session)

    first_plate = create_manufactured_allocated_plate(
        db_session,
        first_property.id,
        employee.id,
    )

    second_plate = create_manufactured_allocated_plate(
        db_session,
        second_property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[first_plate.id, second_plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.mark_ready(dispatch.dispatch_code)

    result = service.mark_dispatched(
        dispatch.dispatch_code,
        performed_by=employee.id,
    )

    assert result.status == "dispatched"

    for plate in [first_plate, second_plate]:
        events = (
            db_session.query(AddressPlateLifecycleEvent)
            .filter(
                AddressPlateLifecycleEvent.plate_id == plate.id,
            )
            .order_by(
                AddressPlateLifecycleEvent.occurred_at.asc(),
            )
            .all()
        )

        assert len(events) == 3
        assert events[0].event_type == "manufactured"
        assert events[1].event_type == "allocated"
        assert events[2].event_type == "dispatched"
        assert events[2].performed_by == employee.id


def test_mark_dispatched_requires_ready_status(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Dispatch cannot transition to the requested status",
    ):
        service.mark_dispatched(
            dispatch.dispatch_code,
            performed_by=employee.id,
        )


def test_mark_delivered(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.mark_ready(dispatch.dispatch_code)
    service.mark_dispatched(
        dispatch.dispatch_code,
        performed_by=employee.id,
    )

    result = service.mark_delivered(dispatch.dispatch_code)

    assert result.status == "delivered"

    latest_event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
        )
        .order_by(
            AddressPlateLifecycleEvent.occurred_at.desc(),
        )
        .first()
    )

    assert latest_event.event_type == "dispatched"


def test_cancel_dispatch_from_draft(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    result = service.cancel_dispatch(dispatch.dispatch_code)

    assert result.status == "cancelled"


def test_cancel_dispatch_from_ready(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.mark_ready(dispatch.dispatch_code)

    result = service.cancel_dispatch(dispatch.dispatch_code)

    assert result.status == "cancelled"


def test_cancel_dispatched_dispatch_is_rejected(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.mark_ready(dispatch.dispatch_code)
    service.mark_dispatched(
        dispatch.dispatch_code,
        performed_by=employee.id,
    )

    with pytest.raises(
        ValueError,
        match="Dispatch cannot transition to the requested status",
    ):
        service.cancel_dispatch(dispatch.dispatch_code)


def test_get_dispatch_and_plates(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    result = service.get_dispatch(dispatch.dispatch_code)

    assert result.id == dispatch.id
    assert result.dispatch_code == dispatch.dispatch_code

    items = service.get_dispatch_plates(
        dispatch.dispatch_code
    )

    assert len(items) == 1
    assert items[0].plate_id == plate.id


def test_get_missing_dispatch_rejected(db_session):
    service = DispatchService(db_session)

    with pytest.raises(
        ValueError,
        match="Dispatch not found",
    ):
        service.get_dispatch("DSP-DOES-NOT-EXIST")


def test_cancel_dispatch_releases_dispatch_items(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    result = service.cancel_dispatch(dispatch.dispatch_code)

    assert result.status == "cancelled"

    items = service.get_dispatch_plates(
        dispatch.dispatch_code
    )

    assert len(items) == 1
    assert items[0].plate_id == plate.id
    assert items[0].released_at is not None


def test_cancelled_dispatch_allows_plate_reassignment(db_session):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    first_dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.cancel_dispatch(
        first_dispatch.dispatch_code
    )

    second_dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="John Doe",
        recipient_phone="+254722222222",
        created_by=employee.id,
    )

    assert second_dispatch.status == "draft"

    first_items = service.get_dispatch_plates(
        first_dispatch.dispatch_code
    )
    second_items = service.get_dispatch_plates(
        second_dispatch.dispatch_code
    )

    assert len(first_items) == 1
    assert len(second_items) == 1

    assert first_items[0].plate_id == plate.id
    assert first_items[0].released_at is not None

    assert second_items[0].plate_id == plate.id
    assert second_items[0].released_at is None


def test_cancel_dispatch_does_not_create_dispatched_lifecycle_event(
    db_session,
):
    employee = create_employee(db_session)
    _, property = create_landlord_and_property(db_session)

    plate = create_manufactured_allocated_plate(
        db_session,
        property.id,
        employee.id,
    )

    service = DispatchService(db_session)

    dispatch = service.create_dispatch(
        plate_ids=[plate.id],
        destination="Nairobi",
        recipient_name="Jane Doe",
        recipient_phone="+254711111111",
        created_by=employee.id,
    )

    service.cancel_dispatch(
        dispatch.dispatch_code
    )

    latest_event = service.lifecycle_service.get_latest_event(
        plate.id
    )

    assert latest_event is not None
    assert latest_event.event_type == "allocated"
