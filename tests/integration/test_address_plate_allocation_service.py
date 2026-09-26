import uuid

import pytest

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.address_plate_request import AddressPlateRequest
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.address_plate_allocation_service import (
    AddressPlateAllocationService,
)


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

    return user, property


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
    user, property = create_landlord_and_property(db_session)

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
        performed_by=user.id,
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
    assert event.performed_by == user.id


def test_allocate_plate_rejects_missing_request(db_session):
    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate request not found",
    ):
        service.allocate_plate(
            request_id=uuid.uuid4(),
            performed_by=uuid.uuid4(),
        )


def test_allocate_plate_rejects_unapproved_request(db_session):
    user, property = create_landlord_and_property(db_session)

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
            performed_by=user.id,
        )


def test_allocate_plate_rejects_property_with_existing_plate(db_session):
    user, property = create_landlord_and_property(db_session)

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
            performed_by=user.id,
        )


def test_allocate_plate_rejects_when_no_plates_are_available(db_session):
    user, property = create_landlord_and_property(db_session)

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
        {"status": "verified"},
        synchronize_session="fetch",
    )

    create_manufactured_plate(
        db_session,
        performed_by=user.id,
        status="verified",
    )

    service = AddressPlateAllocationService(db_session)

    with pytest.raises(
        ValueError,
        match="No address plates available for allocation",
    ):
        service.allocate_plate(
            request_id=request.id,
            performed_by=user.id,
        )


def test_allocate_plate_rejects_unmanufactured_plate(db_session):
    user, property = create_landlord_and_property(db_session)

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
        {"status": "verified"},
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
            performed_by=user.id,
        )

    assert plate.property_id is None
    assert request.status == "approved"


def test_allocate_plate_rejects_fulfilled_request(db_session):
    user, property = create_landlord_and_property(db_session)

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
        performed_by=user.id,
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
            performed_by=user.id,
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
    user, property = create_landlord_and_property(db_session)

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
        {"status": "verified"},
        synchronize_session="fetch",
    )

    _, assigned_property = create_landlord_and_property(db_session)

    assigned_plate = create_manufactured_plate(
        db_session,
        performed_by=user.id,
        property_id=assigned_property.id,
    )

    verified_plate = create_manufactured_plate(
        db_session,
        performed_by=user.id,
        status="verified",
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
        performed_by=user.id,
    )

    assert result.id == available_plate.id
    assert result.property_id == property.id
    assert result.status == "unactivated"

    assert assigned_plate.property_id == assigned_property.id
    assert assigned_plate.status == "unactivated"

    assert verified_plate.property_id is None
    assert verified_plate.status == "verified"

    assert active_plate.property_id is None
    assert active_plate.status == "active"
