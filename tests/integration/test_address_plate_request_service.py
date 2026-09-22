import uuid

import pytest

from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.address_plate_request_service import (
    AddressPlateRequestService,
)


def test_create_request_creates_pending_request(db_session):
    user = User(
        email=f"plate-request-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Plate Request Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Plate Request Test Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    request = service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )

    assert request.id is not None
    assert request.property_id == property.id
    assert request.requested_by == user.id
    assert request.status == "pending"
    assert request.requested_at is not None


def test_create_request_raises_when_property_does_not_exist(db_session):
    service = AddressPlateRequestService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.create_request(
            property_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
        )


def test_create_request_raises_when_property_has_active_plate(db_session):
    user = User(
        email=f"active-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Active Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Active Plate Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()


    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="active",
    )
    db_session.add(plate)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    with pytest.raises(
        ValueError,
        match="Property already has an active address plate",
    ):
        service.create_request(
            property_id=property.id,
            requested_by=user.id,
        )


def test_create_request_raises_when_pending_request_exists(db_session):
    user = User(
        email=f"pending-request-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Pending Request Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Pending Request Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    first_request = service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )

    assert first_request.status == "pending"

    with pytest.raises(
        ValueError,
        match="Property already has a pending address plate request",
    ):
        service.create_request(
            property_id=property.id,
            requested_by=user.id,
        )

def test_approve_request_changes_pending_request_to_approved(db_session):
    user = User(
        email=f"approve-request-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Approve Request Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Approve Request Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    request = service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )

    approved_request = service.approve_request(request.id)

    assert approved_request.id == request.id
    assert approved_request.status == "approved"


def test_approve_request_raises_when_request_does_not_exist(db_session):
    service = AddressPlateRequestService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate request not found",
    ):
        service.approve_request(uuid.uuid4())


def test_approve_request_raises_when_request_is_not_pending(db_session):
    user = User(
        email=f"approve-status-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Approve Status Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Approve Status Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    request = service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )

    request.status = "approved"
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Address plate request is not pending",
    ):
        service.approve_request(request.id)


def test_reject_request_changes_pending_request_to_rejected(db_session):
    user = User(
        email=f"reject-request-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Reject Request Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Reject Request Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    request = service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )

    rejected_request = service.reject_request(request.id)

    assert rejected_request.id == request.id
    assert rejected_request.status == "rejected"


def test_reject_request_raises_when_request_does_not_exist(db_session):
    service = AddressPlateRequestService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate request not found",
    ):
        service.reject_request(uuid.uuid4())


def test_reject_request_raises_when_request_is_not_pending(db_session):
    user = User(
        email=f"reject-status-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Reject Status Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Reject Status Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    request = service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )

    request.status = "rejected"
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Address plate request is not pending",
    ):
        service.reject_request(request.id)
