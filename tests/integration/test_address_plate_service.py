import uuid

from app.models.user import User
from app.services.address_plate_service import AddressPlateService
from app.services.manufacturing_order_service import ManufacturingOrderService


def create_employee(db_session):
    employee = User(
        email=f"plate-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )
    db_session.add(employee)
    db_session.flush()

    return employee


def test_get_plate_by_code_returns_existing_plate(db_session):
    employee = create_employee(db_session)

    manufacturing_service = ManufacturingOrderService(db_session)

    manufacturing_order = manufacturing_service.create_order(
        quantity=1,
        created_by=employee.id,
    )

    manufacturing_service.approve_order(
        order_code=manufacturing_order.order_code,
        approved_by=employee.id,
    )

    manufacturing_service.start_order(
        order_code=manufacturing_order.order_code,
    )

    manufacturing_service.complete_order(
        order_code=manufacturing_order.order_code,
        completed_by=employee.id,
    )

    created_plate = manufacturing_service.get_order_plates(
        manufacturing_order.order_code
    )[0]

    service = AddressPlateService(db_session)

    found_plate = service.get_plate_by_code(
        created_plate.plate_code
    )

    assert found_plate is not None
    assert found_plate.id == created_plate.id
    assert found_plate.plate_code == created_plate.plate_code
    assert found_plate.manufacturing_order_id == manufacturing_order.id
    assert found_plate.status == "unactivated"
