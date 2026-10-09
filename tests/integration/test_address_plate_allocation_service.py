import uuid
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.address_plate_request import AddressPlateRequest
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.address_plate_allocation_service import (
    AddressPlateAllocationService,
)
from app.services.property_access_service import PropertyAccessService


def create_landlord_and_property(db_session):
    user = User(
        email=f"allocation-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Allocation Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Allocation Test Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    employee = User(
        email=f"allocation-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=True,
    )
    db_session.add(employee)
    db_session.flush()

    employee_record = Employee(
        user_id=employee.id,
        employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
        department="Operations",
        position="Test Employee",
    )
    db_session.add(employee_record)
    db_session.flush()

    db_session.add(
        EmployeeClearance(
            employee_id=employee_record.id,
            clearance="plate_operations",
            is_active=True,
        )
    )
    db_session.flush()

    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    return user, property, employee


def create_manufactured_plate(
    db_session,
    *,
    performed_by,
    status="unactivated",
    property_id=None,
):
    plate = AddressPlate(
        property_id=property_id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status=status,
    )
    db_session.add(plate)
    db_session.flush()

    event = AddressPlateLifecycleEvent(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=performed_by,
    )
    db_session.add(event)
    db_session.flush()

    return plate


def test_allocate_plate_to_approved_request(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    create_manufactured_plate(db_session, performed_by=user.id)

    service = AddressPlateAllocationService(db_session)

    result = service.allocate_plate(
        request_id=request.id,
        user=employee,
    )

    assert result.property_id == property.id
    assert result.status == "unactivated"

    assert request.status == "fulfilled"

    event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == result.id,
            AddressPlateLifecycleEvent.event_type == "allocated",
        )
        .first()
    )

    assert event is not None
    assert event.performed_by == employee.id


def test_allocate_plate_rejects_missing_request(db_session):
    _, _, employee = create_landlord_and_property(db_session)

    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate request not found",
    ):
        service.allocate_plate(
            request_id=uuid.uuid4(),
            user=employee,
        )


def test_allocate_plate_rejects_unapproved_request(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="pending",
    )
    db_session.add(request)
    db_session.flush()

    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate request is not approved",
    ):
        service.allocate_plate(
            request_id=request.id,
            user=employee,
        )


def test_allocate_plate_rejects_property_with_existing_plate(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    existing_plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="active",
    )
    db_session.add(existing_plate)
    db_session.flush()

    new_plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(new_plate)
    db_session.flush()

    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property already has an address plate",
    ):
        service.allocate_plate(
            request_id=request.id,
            user=employee,
        )


def test_allocate_plate_rejects_when_no_plates_are_available(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "active"},
        synchronize_session="fetch",
    )

    create_manufactured_plate(
        db_session,
        performed_by=user.id,
        status="active",
    )

    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="No address plates available for allocation",
    ):
        service.allocate_plate(
            request_id=request.id,
            user=employee,
        )


def test_allocate_plate_rejects_unmanufactured_plate(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "active"},
        synchronize_session="fetch",
    )

    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="No address plates available for allocation",
    ):
        service.allocate_plate(
            request_id=request.id,
            user=employee,
        )

    assert plate.property_id is None
    assert request.status == "approved"


def test_allocate_plate_rejects_fulfilled_request(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    first_plate = create_manufactured_plate(db_session, performed_by=user.id)
    second_plate = create_manufactured_plate(db_session, performed_by=user.id)

    service = AddressPlateAllocationService(db_session)

    result = service.allocate_plate(
        request_id=request.id,
        user=employee,
    )

    assert result.property_id == property.id
    assert result.status == "unactivated"
    assert request.status == "fulfilled"

    with pytest.raises(
        ValueError,
        match="Address plate request is not approved",
    ):
        service.allocate_plate(
            request_id=request.id,
            user=employee,
        )

    db_session.refresh(first_plate)
    db_session.refresh(second_plate)

    allocated_plates = {
        first_plate.id: first_plate,
        second_plate.id: second_plate,
    }

    if result.id in allocated_plates:
        assert allocated_plates[result.id].property_id == property.id
        assert allocated_plates[result.id].status == "unactivated"


def test_allocate_plate_uses_only_available_inventory(db_session):
    user, property, employee = create_landlord_and_property(db_session)

    request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "active"},
        synchronize_session="fetch",
    )

    _, assigned_property, _ = create_landlord_and_property(db_session)

    assigned_plate = create_manufactured_plate(
        db_session,
        performed_by=user.id,
        property_id=assigned_property.id,
    )

    unavailable_plate = create_manufactured_plate(
        db_session,
        performed_by=user.id,
        status="active",
    )

    active_plate = create_manufactured_plate(
        db_session,
        performed_by=user.id,
        status="active",
    )

    available_plate = create_manufactured_plate(db_session, performed_by=user.id)

    service = AddressPlateAllocationService(db_session)

    result = service.allocate_plate(
        request_id=request.id,
        user=employee,
    )

    assert result.id == available_plate.id
    assert result.property_id == property.id
    assert result.status == "unactivated"

    assert assigned_plate.property_id == assigned_property.id
    assert assigned_plate.status == "unactivated"

    assert unavailable_plate.property_id is None
    assert unavailable_plate.status == "active"

    assert active_plate.property_id is None
    assert active_plate.status == "active"


def test_allocate_plate_serializes_concurrent_allocations_for_same_property(
    db_session,
):
    user, property, employee = create_landlord_and_property(db_session)

    first_request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    second_request = AddressPlateRequest(
        property_id=property.id,
        requested_by=user.id,
        status="approved",
    )
    db_session.add_all([first_request, second_request])
    db_session.flush()

    create_manufactured_plate(
        db_session,
        performed_by=user.id,
    )
    create_manufactured_plate(
        db_session,
        performed_by=user.id,
    )

    property_id = property.id
    first_request_id = first_request.id
    second_request_id = second_request.id
    employee_id = employee.id

    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_employee = first_session.get(User, employee_id)
    second_employee = second_session.get(User, employee_id)

    assert first_employee is not None
    assert second_employee is not None

    second_started = Event()
    second_finished = Event()
    second_result = {}
    second_error = {}
    thread = None

    try:
        first_service = AddressPlateAllocationService(first_session)

        locked_property = (
            first_service.property_repository.get_by_id_for_update(
                property_id
            )
        )

        assert locked_property is not None

        def allocate_from_second_transaction():
            try:
                second_service = AddressPlateAllocationService(
                    second_session
                )
                second_started.set()

                result = second_service.allocate_plate(
                    request_id=second_request_id,
                    user=second_employee,
                )

                second_result["plate_id"] = result.id
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=allocate_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_result = first_service.allocate_plate(
            request_id=first_request_id,
            user=first_employee,
        )

        assert first_result.property_id == property_id

        first_session.commit()

        assert second_finished.wait(timeout=2)
        thread.join(timeout=2)

        assert "plate_id" not in second_result
        assert isinstance(
            second_error.get("error"),
            ValueError,
        )
        assert str(second_error["error"]) == (
            "Property already has an address plate"
        )

        second_session.rollback()

        allocated_plates = (
            second_session.query(AddressPlate)
            .filter(AddressPlate.property_id == property_id)
            .all()
        )

        assert len(allocated_plates) == 1
        assert allocated_plates[0].id == first_result.id

    finally:
        if thread is not None:
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()
