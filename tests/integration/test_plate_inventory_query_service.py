import uuid

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.services.plate_inventory_query_service import (
    PlateInventoryQueryService,
)


def create_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"inventory-query-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_landlord(db_session):
    user = create_user(db_session)

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Inventory Test Landlord",
        phone=f"+2547{uuid.uuid4().int % 10**8:08d}",
    )
    db_session.add(landlord)
    db_session.flush()
    return landlord


def create_property(db_session, landlord, name="Inventory Test Property"):
    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name=name,
        property_type="residential",
        status="active",
    )
    db_session.add(property_record)
    db_session.flush()
    return property_record


def create_plate(db_session, property_id=None):
    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
        property_id=property_id,
    )
    db_session.add(plate)
    db_session.flush()
    return plate


def record_lifecycle(db_session, plate_id, event_type):
    employee = User(
        id=uuid.uuid4(),
        email=f"lifecycle-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )
    db_session.add(employee)
    db_session.flush()

    service = AddressPlateLifecycleService(db_session)

    return service.record_event(
        plate_id=plate_id,
        event_type=event_type,
        performed_by=employee.id,
    )


def test_list_inventory_includes_plate_without_lifecycle_event(db_session):
    plate = create_plate(db_session)

    service = PlateInventoryQueryService(db_session)

    records = service.list_inventory()

    result = next(
        record for record in records
        if record["id"] == plate.id
    )

    assert result["plate_code"] == plate.plate_code
    assert result["property_id"] is None
    assert result["property_code"] is None
    assert result["property_name"] is None
    assert result["status"] == "unactivated"
    assert result["lifecycle_status"] is None
    assert result["activated_at"] is None


def test_list_inventory_includes_latest_lifecycle_status(db_session):
    plate = create_plate(db_session)

    record_lifecycle(db_session, plate.id, "manufactured")
    record_lifecycle(db_session, plate.id, "allocated")

    service = PlateInventoryQueryService(db_session)

    records = service.list_inventory()

    result = next(
        record for record in records
        if record["id"] == plate.id
    )

    assert result["lifecycle_status"] == "allocated"


def test_list_inventory_includes_property_details(db_session):
    landlord = create_landlord(db_session)
    property_record = create_property(db_session, landlord)
    plate = create_plate(
        db_session,
        property_id=property_record.id,
    )

    record_lifecycle(db_session, plate.id, "manufactured")

    service = PlateInventoryQueryService(db_session)

    records = service.list_inventory()

    result = next(
        record for record in records
        if record["id"] == plate.id
    )

    assert result["property_id"] == property_record.id
    assert result["property_code"] == property_record.property_code
    assert result["property_name"] == property_record.name
    assert result["lifecycle_status"] == "manufactured"


def test_list_inventory_orders_newest_plates_first(db_session):
    first_plate = create_plate(db_session)
    second_plate = create_plate(db_session)

    service = PlateInventoryQueryService(db_session)

    records = service.list_inventory()

    first_index = next(
        index
        for index, record in enumerate(records)
        if record["id"] == first_plate.id
    )
    second_index = next(
        index
        for index, record in enumerate(records)
        if record["id"] == second_plate.id
    )

    assert second_index < first_index
