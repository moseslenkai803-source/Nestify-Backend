import uuid

from app.models.address_plate import AddressPlate
from app.models.manufacturing_order import ManufacturingOrder
from app.models.user import User
from app.services.plate_inventory_service import PlateInventoryService


def create_employee(db_session):
    employee = User(
        email=f"inventory-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )
    db_session.add(employee)
    db_session.flush()

    return employee


def create_manufacturing_order(db_session, employee):
    order = ManufacturingOrder(
        order_code=f"MO-{uuid.uuid4().hex[:12].upper()}",
        quantity=1,
        status="in_production",
        created_by=employee.id,
    )
    db_session.add(order)
    db_session.flush()

    return order


def test_create_plate_inventory_record(db_session):
    employee = create_employee(db_session)
    order = create_manufacturing_order(db_session, employee)

    service = PlateInventoryService(db_session)

    plate = service.create_plate(
        manufacturing_order_id=order.id,
    )

    assert isinstance(plate, AddressPlate)
    assert plate.id is not None
    assert plate.plate_code.startswith("PLATE-")
    assert plate.manufacturing_order_id == order.id
    assert plate.status == "unactivated"
    assert plate.property_id is None


def test_create_plate_inventory_records_have_unique_plate_codes(
    db_session,
):
    employee = create_employee(db_session)
    order = create_manufacturing_order(db_session, employee)

    service = PlateInventoryService(db_session)

    first_plate = service.create_plate(
        manufacturing_order_id=order.id,
    )
    second_plate = service.create_plate(
        manufacturing_order_id=order.id,
    )

    assert first_plate.id != second_plate.id
    assert first_plate.plate_code != second_plate.plate_code
