import uuid
from datetime import UTC, datetime, timedelta
from threading import Event, Thread

from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.manufacturing_order import ManufacturingOrder
from app.models.property import Property
from app.models.user import User
from app.db.session import SessionLocal
from app.repositories.address_plate_repository import AddressPlateRepository


def test_get_by_plate_code_returns_address_plate(db_session):
    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code="NEST-PLATE-001",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)


    result = repository.get_by_plate_code("NEST-PLATE-001")


    assert result is not None
    assert result.id == plate.id
    assert result.plate_code == "NEST-PLATE-001"
    assert result.status == "unactivated"
    assert result.property_id is None


def test_get_by_property_id_returns_address_plate(db_session):
    user = User(
        id=uuid.uuid4(),
        email="plate-property-test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Plate Property Test Landlord",
        phone="+254700000002",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-PLATE-PROP-001",
        name="Plate Property Test",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code="NEST-PLATE-002",
        status="active",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_by_property_id(property_record.id)

    assert result is not None
    assert result.id == plate.id
    assert result.property_id == property_record.id
    assert result.plate_code == "NEST-PLATE-002"
    assert result.status == "active"


def test_get_unactivated_returns_only_unactivated_plates(db_session):
    unactivated_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code="NEST-PLATE-003",
        status="unactivated",
    )

    active_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code="NEST-PLATE-004",
        status="active",
    )

    db_session.add(unactivated_plate)
    db_session.add(active_plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_unactivated()

    result_ids = {plate.id for plate in result}

    assert unactivated_plate.id in result_ids
    assert active_plate.id not in result_ids
    assert all(plate.status == "unactivated" for plate in result)


def test_get_active_by_property_id_returns_only_active_plate(db_session):
    user = User(
        id=uuid.uuid4(),
        email="active-plate-property@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Active Plate Landlord",
        phone="+254700000003",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-ACTIVE-PLATE-PROP-001",
        name="Active Plate Property",
        property_type="residential",
        status="active",
    )

    active_plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code="NEST-ACTIVE-PLATE-001",
        status="active",
    )

    unactivated_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code="NEST-ACTIVE-PLATE-002",
        status="unactivated",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(active_plate)
    db_session.add(unactivated_plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_active_by_property_id(property_record.id)

    assert result is not None
    assert result.id == active_plate.id
    assert result.property_id == property_record.id
    assert result.plate_code == "NEST-ACTIVE-PLATE-001"
    assert result.status == "active"


def test_get_by_id_returns_address_plate(db_session):
    plate = AddressPlate(
        plate_code="NEST-PLATE-ID-001",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_by_id(plate.id)

    assert result is not None
    assert result.id == plate.id
    assert result.plate_code == "NEST-PLATE-ID-001"


def test_get_by_manufacturing_order_id_returns_only_matching_plates(
    db_session,
):
    user = User(
        id=uuid.uuid4(),
        email="manufacturing-repository-test@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    first_order = ManufacturingOrder(
        id=uuid.uuid4(),
        order_code="MO-REPO-001",
        quantity=2,
        status="completed",
        created_by=user.id,
    )

    second_order = ManufacturingOrder(
        id=uuid.uuid4(),
        order_code="MO-REPO-002",
        quantity=1,
        status="completed",
        created_by=user.id,
    )

    first_plate = AddressPlate(
        id=uuid.uuid4(),
        manufacturing_order_id=first_order.id,
        plate_code="NEST-MO-PLATE-001",
        status="unactivated",
    )

    second_plate = AddressPlate(
        id=uuid.uuid4(),
        manufacturing_order_id=first_order.id,
        plate_code="NEST-MO-PLATE-002",
        status="unactivated",
    )

    unrelated_plate = AddressPlate(
        id=uuid.uuid4(),
        manufacturing_order_id=second_order.id,
        plate_code="NEST-MO-PLATE-003",
        status="unactivated",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(first_order)
    db_session.add(second_order)
    db_session.flush()

    db_session.add(first_plate)
    db_session.add(second_plate)
    db_session.add(unrelated_plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_by_manufacturing_order_id(
        first_order.id
    )

    assert len(result) == 2
    assert {plate.id for plate in result} == {
        first_plate.id,
        second_plate.id,
    }
    assert unrelated_plate.id not in {
        plate.id for plate in result
    }




def test_get_next_manufactured_plate_for_update_returns_oldest_eligible_plate(
    db_session,
):
    from app.models.address_plate_lifecycle_event import (
        AddressPlateLifecycleEvent,
    )

    user = User(
        id=uuid.uuid4(),
        email=f"allocation-lock-test-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Allocation Lock Test Landlord",
        phone="+254700000004",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-LOCK-PROP-{uuid.uuid4()}",
        name="Allocation Lock Test Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()

    base_time = datetime(2020, 1, 1, tzinfo=UTC)

    oldest_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"NEST-LOCK-{uuid.uuid4()}-001",
        status="unactivated",
        created_at=base_time,
    )

    newer_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"NEST-LOCK-{uuid.uuid4()}-002",
        status="unactivated",
        created_at=base_time + timedelta(seconds=1),
    )

    allocated_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"NEST-LOCK-{uuid.uuid4()}-003",
        status="unactivated",
        property_id=property_record.id,
        created_at=base_time - timedelta(seconds=1),
    )

    unmanufactured_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"NEST-LOCK-{uuid.uuid4()}-004",
        status="unactivated",
        created_at=base_time - timedelta(seconds=2),
    )

    db_session.add_all(
        [
            oldest_plate,
            newer_plate,
            allocated_plate,
            unmanufactured_plate,
        ]
    )
    db_session.flush()

    db_session.add_all(
        [
            AddressPlateLifecycleEvent(
                plate_id=oldest_plate.id,
                event_type="manufactured",
                performed_by=user.id,
            ),
            AddressPlateLifecycleEvent(
                plate_id=newer_plate.id,
                event_type="manufactured",
                performed_by=user.id,
            ),
            AddressPlateLifecycleEvent(
                plate_id=allocated_plate.id,
                event_type="manufactured",
                performed_by=user.id,
            ),
            AddressPlateLifecycleEvent(
                plate_id=allocated_plate.id,
                event_type="allocated",
                performed_by=user.id,
            ),
        ]
    )
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_next_manufactured_plate_for_update()

    assert result is not None
    assert result.id == oldest_plate.id
    assert result.property_id is None
    assert result.status == "unactivated"


def test_get_next_manufactured_plate_for_update_waits_for_locked_plate(
    db_session,
):
    from app.models.address_plate_lifecycle_event import (
        AddressPlateLifecycleEvent,
    )

    user = User(
        id=uuid.uuid4(),
        email=f"allocation-concurrency-test-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Allocation Concurrency Landlord",
        phone="+254700000005",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-CONCURRENT-PROP-{uuid.uuid4()}",
        name="Allocation Concurrency Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()

    first_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"NEST-CONCURRENT-{uuid.uuid4()}-001",
        status="unactivated",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    second_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"NEST-CONCURRENT-{uuid.uuid4()}-002",
        status="unactivated",
        created_at=datetime(2020, 1, 1, tzinfo=UTC) + timedelta(seconds=1),
    )

    db_session.add_all([first_plate, second_plate])
    db_session.flush()

    db_session.add_all(
        [
            AddressPlateLifecycleEvent(
                plate_id=first_plate.id,
                event_type="manufactured",
                performed_by=user.id,
            ),
            AddressPlateLifecycleEvent(
                plate_id=second_plate.id,
                event_type="manufactured",
                performed_by=user.id,
            ),
        ]
    )
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_locked = Event()
    second_started = Event()
    second_finished = Event()
    second_result = {}
    second_error = {}

    try:
        first_repository = AddressPlateRepository(first_session)

        locked_plate = (
            first_repository.get_next_manufactured_plate_for_update()
        )

        assert locked_plate is not None
        assert locked_plate.id == first_plate.id

        first_locked.set()

        def select_from_second_transaction():
            try:
                second_repository = AddressPlateRepository(second_session)
                second_started.set()

                result = (
                    second_repository
                    .get_next_manufactured_plate_for_update()
                )

                second_result["plate_id"] = (
                    result.id if result is not None else None
                )
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=select_from_second_transaction)
        thread.start()

        assert first_locked.is_set()
        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        locked_plate.property_id = property_record.id
        first_session.commit()

        assert second_finished.wait(timeout=2)

        thread.join(timeout=2)

        assert "error" not in second_error
        assert second_result["plate_id"] is not None
        assert second_result["plate_id"] != first_plate.id

    finally:
        if thread.is_alive():
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()
