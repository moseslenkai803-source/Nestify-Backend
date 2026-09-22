import uuid
from datetime import UTC, datetime, timedelta

from app.models.address_plate_request import AddressPlateRequest
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.repositories.address_plate_request_repository import (
    AddressPlateRequestRepository,
)


def create_property(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"plate-request-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Plate Request Test Landlord",
        phone="+254700000010",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-REQUEST-{uuid.uuid4().hex[:8].upper()}",
        name="Plate Request Test Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    return user, property_record


def test_add_returns_address_plate_request(db_session):
    user, property_record = create_property(db_session)

    request = AddressPlateRequest(
        property_id=property_record.id,
        requested_by=user.id,
        status="pending",
    )

    repository = AddressPlateRequestRepository(db_session)

    result = repository.add(request)

    assert result.id is not None
    assert result.property_id == property_record.id
    assert result.requested_by == user.id
    assert result.status == "pending"
    assert result.requested_at is not None


def test_get_by_id_returns_address_plate_request(db_session):
    user, property_record = create_property(db_session)

    request = AddressPlateRequest(
        property_id=property_record.id,
        requested_by=user.id,
        status="pending",
    )

    db_session.add(request)
    db_session.flush()

    repository = AddressPlateRequestRepository(db_session)

    result = repository.get_by_id(request.id)

    assert result is not None
    assert result.id == request.id
    assert result.property_id == property_record.id
    assert result.requested_by == user.id


def test_get_by_property_id_returns_requests_newest_first(db_session):
    user, property_record = create_property(db_session)

    older_request = AddressPlateRequest(
        property_id=property_record.id,
        requested_by=user.id,
        status="fulfilled",
        requested_at=datetime.now(UTC) - timedelta(days=2),
    )

    newer_request = AddressPlateRequest(
        property_id=property_record.id,
        requested_by=user.id,
        status="pending",
        requested_at=datetime.now(UTC) - timedelta(days=1),
    )

    db_session.add(older_request)
    db_session.add(newer_request)
    db_session.flush()

    repository = AddressPlateRequestRepository(db_session)

    result = repository.get_by_property_id(property_record.id)

    assert len(result) == 2
    assert result[0].id == newer_request.id
    assert result[1].id == older_request.id


def test_get_pending_by_property_id_returns_pending_request(db_session):
    user, property_record = create_property(db_session)

    pending_request = AddressPlateRequest(
        property_id=property_record.id,
        requested_by=user.id,
        status="pending",
    )

    db_session.add(pending_request)
    db_session.flush()

    repository = AddressPlateRequestRepository(db_session)

    result = repository.get_pending_by_property_id(property_record.id)

    assert result is not None
    assert result.id == pending_request.id
    assert result.status == "pending"


def test_get_pending_by_property_id_returns_none_when_no_pending_request(
    db_session,
):
    user, property_record = create_property(db_session)

    fulfilled_request = AddressPlateRequest(
        property_id=property_record.id,
        requested_by=user.id,
        status="fulfilled",
    )

    db_session.add(fulfilled_request)
    db_session.flush()

    repository = AddressPlateRequestRepository(db_session)

    result = repository.get_pending_by_property_id(property_record.id)

    assert result is None
