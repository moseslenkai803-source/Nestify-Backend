import uuid
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal

from app.models.address_plate import AddressPlate
from app.models.address_plate_request import AddressPlateRequest
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


def test_approve_and_reject_request_serialize_concurrent_transitions(db_session):
    user = User(
        email=f"concurrent-request-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Concurrent Request Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Concurrent Request Property",
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
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    try:
        first_service = AddressPlateRequestService(first_session)
        second_service = AddressPlateRequestService(second_session)

        locked_request = (
            first_service.address_plate_request_repository
            .get_by_id_for_update(request.id)
        )

        assert locked_request is not None
        assert locked_request.status == "pending"

        started = Event()
        result = {}

        def reject_in_second_session():
            started.set()
            try:
                second_service.reject_request(request.id)
            except Exception as exc:
                result["exception"] = exc

        thread = Thread(target=reject_in_second_session)
        thread.start()

        assert started.wait(timeout=2)
        thread.join(timeout=0.5)

        assert thread.is_alive()

        approved_request = first_service.approve_request(request.id)

        assert approved_request.status == "approved"

        first_session.commit()

        thread.join(timeout=2)

        assert not thread.is_alive()
        assert isinstance(result.get("exception"), ValueError)
        assert str(result["exception"]) == (
            "Address plate request is not pending"
        )

        first_session.expire_all()

        final_request = (
            first_service.address_plate_request_repository
            .get_by_id(request.id)
        )

        assert final_request is not None
        assert final_request.status == "approved"

    finally:
        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()


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


def test_create_request_raises_when_property_has_allocated_plate(db_session):
    user = User(
        email=f"allocated-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Allocated Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Allocated Plate Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    service = AddressPlateRequestService(db_session)

    with pytest.raises(
        ValueError,
        match="Property already has an address plate",
    ):
        service.create_request(
            property_id=property.id,
            requested_by=user.id,
        )

def test_create_request_serializes_concurrent_requests_for_same_property(
    db_session,
):
    user = User(
        email=f"concurrent-request-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Concurrent Request Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Concurrent Request Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    property_id = property.id
    user_id = user.id
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    second_started = Event()
    second_finished = Event()
    second_error = {}
    thread = None

    try:
        first_service = AddressPlateRequestService(first_session)

        locked_property = (
            first_service.property_repository.get_by_id_for_update(
                property_id
            )
        )

        assert locked_property is not None

        def create_from_second_transaction():
            try:
                second_service = AddressPlateRequestService(second_session)
                second_started.set()

                second_service.create_request(
                    property_id=property_id,
                    requested_by=user_id,
                )
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=create_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_request = first_service.create_request(
            property_id=property_id,
            requested_by=user_id,
        )
        assert first_request.status == "pending"

        first_session.commit()

        assert second_finished.wait(timeout=2)
        thread.join(timeout=2)

        assert isinstance(second_error.get("error"), ValueError)
        assert str(second_error["error"]) == (
            "Property already has a pending address plate request"
        )

        db_session.expire_all()

        requests = (
            db_session.query(AddressPlateRequest)
            .filter(AddressPlateRequest.property_id == property_id)
            .all()
        )

        assert len(requests) == 1
        assert requests[0].status == "pending"


    finally:
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()
