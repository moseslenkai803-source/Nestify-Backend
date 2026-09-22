import uuid
from datetime import UTC, datetime, timedelta

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.repositories.address_plate_lifecycle_event_repository import (
    AddressPlateLifecycleEventRepository,
)


def test_add_persists_address_plate_lifecycle_event(db_session):
    user = User(
        id=uuid.uuid4(),
        email="plate-event-add@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email="plate-event-landlord@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Plate Event Test Landlord",
        phone="+254700000020",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-PLATE-EVENT-001",
        name="Plate Event Property",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code="PLATE-EVENT-001",
        status="active",
    )

    event = AddressPlateLifecycleEvent(
        plate_id=plate.id,
        event_type="activated",
        performed_by=user.id,
        occurred_at=datetime.now(UTC),
        notes="Plate activated successfully",
    )

    db_session.add(user)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    repository = AddressPlateLifecycleEventRepository(db_session)

    result = repository.add(event)

    assert result is event
    assert result.id is not None
    assert result.plate_id == plate.id
    assert result.event_type == "activated"
    assert result.performed_by == user.id
    assert result.notes == "Plate activated successfully"


def test_get_by_plate_id_returns_events_in_chronological_order(db_session):
    user = User(
        id=uuid.uuid4(),
        email="plate-event-history@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email="plate-event-history-landlord@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Plate Event History Landlord",
        phone="+254700000021",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-PLATE-EVENT-002",
        name="Plate Event History Property",
        property_type="commercial",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code="PLATE-EVENT-002",
        status="active",
    )

    first_event = AddressPlateLifecycleEvent(
        id=uuid.uuid4(),
        plate_id=plate.id,
        event_type="requested",
        performed_by=user.id,
        occurred_at=datetime.now(UTC) - timedelta(minutes=10),
        notes="Plate requested",
    )

    second_event = AddressPlateLifecycleEvent(
        id=uuid.uuid4(),
        plate_id=plate.id,
        event_type="approved",
        performed_by=user.id,
        occurred_at=datetime.now(UTC) - timedelta(minutes=5),
        notes="Plate approved",
    )

    third_event = AddressPlateLifecycleEvent(
        id=uuid.uuid4(),
        plate_id=plate.id,
        event_type="allocated",
        performed_by=user.id,
        occurred_at=datetime.now(UTC),
        notes="Plate allocated",
    )

    other_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code="PLATE-EVENT-003",
        status="unactivated",
    )

    other_event = AddressPlateLifecycleEvent(
        id=uuid.uuid4(),
        plate_id=other_plate.id,
        event_type="requested",
        performed_by=user.id,
        occurred_at=datetime.now(UTC),
        notes="Other plate event",
    )

    db_session.add(user)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.add(other_plate)
    db_session.flush()

    db_session.add_all([
        first_event,
        second_event,
        third_event,
        other_event,
    ])
    db_session.flush()

    repository = AddressPlateLifecycleEventRepository(db_session)

    result = repository.get_by_plate_id(plate.id)

    assert len(result) == 3
    assert result[0].id == first_event.id
    assert result[0].event_type == "requested"
    assert result[1].id == second_event.id
    assert result[1].event_type == "approved"
    assert result[2].id == third_event.id
    assert result[2].event_type == "allocated"


def test_get_latest_by_plate_id_returns_newest_event(db_session):
    user = User(
        id=uuid.uuid4(),
        email="plate-event-latest@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email="plate-event-latest-landlord@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Latest Plate Event Landlord",
        phone="+254700000022",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-PLATE-EVENT-004",
        name="Latest Plate Event Property",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code="PLATE-EVENT-004",
        status="active",
    )

    older_event = AddressPlateLifecycleEvent(
        id=uuid.uuid4(),
        plate_id=plate.id,
        event_type="installed",
        performed_by=user.id,
        occurred_at=datetime.now(UTC) - timedelta(minutes=10),
        notes="Installation recorded",
    )

    latest_event = AddressPlateLifecycleEvent(
        id=uuid.uuid4(),
        plate_id=plate.id,
        event_type="verified",
        performed_by=user.id,
        occurred_at=datetime.now(UTC),
        notes="Installation verified",
    )

    db_session.add(user)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    db_session.add_all([
        older_event,
        latest_event,
    ])
    db_session.flush()

    repository = AddressPlateLifecycleEventRepository(db_session)

    result = repository.get_latest_by_plate_id(plate.id)

    assert result is not None
    assert result.id == latest_event.id
    assert result.event_type == "verified"
    assert result.notes == "Installation verified"
