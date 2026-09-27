import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.manufacturing_order_service import ManufacturingOrderService


def create_plate_operations_employee(db_session):
    employee = User(
        email=f"plate-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee.id, create_access_token(
        subject=str(employee.id),
    )


def test_get_address_plate_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        manufacturing_service = ManufacturingOrderService(db_session)

        manufacturing_order = manufacturing_service.create_order(
            quantity=1,
            created_by=employee_id,
        )

        manufacturing_service.approve_order(
            order_code=manufacturing_order.order_code,
            approved_by=employee_id,
        )

        manufacturing_service.start_order(
            order_code=manufacturing_order.order_code,
        )

        manufacturing_service.complete_order(
            order_code=manufacturing_order.order_code,
            completed_by=employee_id,
        )

        plate = manufacturing_service.get_order_plates(
            manufacturing_order.order_code
        )[0]

        response = client.get(
            f"/api/v1/address-plates/{plate.plate_code}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(plate.id)
        assert data["plate_code"] == plate.plate_code
        assert data["status"] == "unactivated"
        assert data["property_id"] is None
        assert data["activated_at"] is None

    finally:
        app.dependency_overrides.clear()


def test_get_address_plate_api_returns_404_for_missing_plate(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        response = client.get(
            f"/api/v1/address-plates/PLATE-{uuid.uuid4().hex[:12].upper()}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Plate not found"

    finally:
        app.dependency_overrides.clear()
