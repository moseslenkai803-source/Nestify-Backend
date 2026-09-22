import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.manufacturing_order import ManufacturingOrder
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import AddressPlateLifecycleEvent
from app.models.user import User


def create_plate_operations_employee(db_session):
    employee = User(
        email=f"manufacturing-api-{uuid.uuid4()}@example.com",
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


def test_create_manufacturing_order_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/manufacturing-orders",
            json={
                "quantity": 25,
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["order_code"].startswith("MO-")
        assert data["quantity"] == 25
        assert data["status"] == "draft"
        assert data["created_by"] == str(employee_id)
        assert data["approved_by"] is None
        assert data["started_at"] is None
        assert data["completed_at"] is None
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

        order = (
            db_session.query(ManufacturingOrder)
            .filter(
                ManufacturingOrder.order_code == data["order_code"],
            )
            .one()
        )

        assert order.quantity == 25
        assert order.status == "draft"
        assert order.created_by == employee_id

    finally:
        app.dependency_overrides.clear()


def create_user_access_token(
    db_session,
    *,
    role: str,
    clearance: str | None = None,
):
    user = User(
        email=f"manufacturing-auth-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        clearance=clearance,
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    return create_access_token(
        subject=str(user.id),
    )


def test_create_manufacturing_order_api_requires_plate_operations_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        restricted_token = create_user_access_token(
            db_session,
            role="employee",
            clearance="support",
        )

        response = client.post(
            "/api/v1/manufacturing-orders",
            json={
                "quantity": 25,
            },
            headers={
                "Authorization": f"Bearer {restricted_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_manufacturing_order_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-TEST-{uuid.uuid4().hex[:8].upper()}",
            quantity=50,
            status="draft",
            created_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.get(
            f"/api/v1/manufacturing-orders/{order.order_code}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(order.id)
        assert data["order_code"] == order.order_code
        assert data["quantity"] == 50
        assert data["status"] == "draft"
        assert data["created_by"] == str(employee_id)

    finally:
        app.dependency_overrides.clear()


def test_get_manufacturing_order_api_returns_404_for_missing_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.get(
            "/api/v1/manufacturing-orders/MO-DOES-NOT-EXIST",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Manufacturing order not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_approve_manufacturing_order_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-APPROVE-{uuid.uuid4().hex[:8].upper()}",
            quantity=10,
            status="draft",
            created_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "approved"
        assert data["approved_by"] == str(employee_id)

        db_session.refresh(order)

        assert order.status == "approved"
        assert order.approved_by == employee_id

    finally:
        app.dependency_overrides.clear()


def test_approve_manufacturing_order_api_returns_404_for_missing_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/manufacturing-orders/MO-DOES-NOT-EXIST/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Manufacturing order not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_approve_manufacturing_order_api_rejects_non_draft_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-REAPPROVE-{uuid.uuid4().hex[:8].upper()}",
            quantity=10,
            status="approved",
            created_by=employee_id,
            approved_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Manufacturing order cannot be approved in its current status"
        )

        db_session.refresh(order)

        assert order.status == "approved"
        assert order.approved_by == employee_id

    finally:
        app.dependency_overrides.clear()

def test_start_manufacturing_order_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-START-{uuid.uuid4().hex[:8].upper()}",
            quantity=10,
            status="approved",
            created_by=employee_id,
            approved_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/start",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "in_production"
        assert data["started_at"] is not None

        db_session.refresh(order)

        assert order.status == "in_production"
        assert order.started_at is not None

    finally:
        app.dependency_overrides.clear()


def test_start_manufacturing_order_api_returns_404_for_missing_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/manufacturing-orders/MO-DOES-NOT-EXIST/start",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Manufacturing order not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_start_manufacturing_order_api_rejects_non_approved_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-NOT-APPROVED-{uuid.uuid4().hex[:8].upper()}",
            quantity=10,
            status="draft",
            created_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/start",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Manufacturing order cannot be started in its current status"
        )

        db_session.refresh(order)

        assert order.status == "draft"
        assert order.started_at is None

    finally:
        app.dependency_overrides.clear()

def test_complete_manufacturing_order_api_creates_plate_inventory(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-COMPLETE-{uuid.uuid4().hex[:8].upper()}",
            quantity=3,
            status="in_production",
            created_by=employee_id,
            approved_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/complete",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "completed"
        assert data["completed_at"] is not None

        db_session.refresh(order)

        assert order.status == "completed"
        assert order.completed_at is not None

        plates = (
            db_session.query(AddressPlate)
            .filter(
                AddressPlate.manufacturing_order_id == order.id,
            )
            .all()
        )

        assert len(plates) == 3

        for plate in plates:
            assert plate.plate_code.startswith("PLATE-")
            assert plate.status == "unactivated"
            assert plate.property_id is None

            events = (
                db_session.query(AddressPlateLifecycleEvent)
                .filter(
                    AddressPlateLifecycleEvent.plate_id == plate.id,
                )
                .all()
            )

            assert len(events) == 1
            assert events[0].event_type == "manufactured"
            assert events[0].performed_by == employee_id

    finally:
        app.dependency_overrides.clear()


def test_complete_manufacturing_order_api_returns_404_for_missing_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/manufacturing-orders/MO-DOES-NOT-EXIST/complete",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Manufacturing order not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_complete_manufacturing_order_api_rejects_non_production_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-NOT-PRODUCTION-{uuid.uuid4().hex[:8].upper()}",
            quantity=3,
            status="approved",
            created_by=employee_id,
            approved_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/complete",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Manufacturing order cannot be completed in its current status"
        )

        db_session.refresh(order)

        assert order.status == "approved"
        assert order.completed_at is None

        plates = (
            db_session.query(AddressPlate)
            .filter(
                AddressPlate.manufacturing_order_id == order.id,
            )
            .all()
        )

        assert plates == []

    finally:
        app.dependency_overrides.clear()

def test_cancel_manufacturing_order_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-CANCEL-{uuid.uuid4().hex[:8].upper()}",
            quantity=10,
            status="draft",
            created_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/cancel",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "cancelled"

        db_session.refresh(order)

        assert order.status == "cancelled"

    finally:
        app.dependency_overrides.clear()


def test_cancel_manufacturing_order_api_returns_404_for_missing_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/manufacturing-orders/MO-DOES-NOT-EXIST/cancel",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Manufacturing order not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_cancel_manufacturing_order_api_rejects_completed_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-CANCEL-COMPLETED-{uuid.uuid4().hex[:8].upper()}",
            quantity=10,
            status="completed",
            created_by=employee_id,
            approved_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        response = client.post(
            f"/api/v1/manufacturing-orders/{order.order_code}/cancel",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Manufacturing order cannot be cancelled in its current status"
        )

        db_session.refresh(order)

        assert order.status == "completed"

    finally:
        app.dependency_overrides.clear()

def test_get_manufacturing_order_plates_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_plate_operations_employee(
            db_session
        )

        order = ManufacturingOrder(
            order_code=f"MO-PLATES-{uuid.uuid4().hex[:8].upper()}",
            quantity=2,
            status="completed",
            created_by=employee_id,
            approved_by=employee_id,
        )

        db_session.add(order)
        db_session.flush()

        plate_one = AddressPlate(
            manufacturing_order_id=order.id,
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            status="unactivated",
        )

        plate_two = AddressPlate(
            manufacturing_order_id=order.id,
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            status="unactivated",
        )

        db_session.add_all([plate_one, plate_two])
        db_session.flush()

        response = client.get(
            f"/api/v1/manufacturing-orders/{order.order_code}/plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2

        returned_plate_codes = {
            plate["plate_code"]
            for plate in data
        }

        assert returned_plate_codes == {
            plate_one.plate_code,
            plate_two.plate_code,
        }

        for plate in data:
            assert plate["status"] == "unactivated"
            assert plate["property_id"] is None

    finally:
        app.dependency_overrides.clear()


def test_get_manufacturing_order_plates_api_returns_404_for_missing_order(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.get(
            "/api/v1/manufacturing-orders/MO-DOES-NOT-EXIST/plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Manufacturing order not found"
        )

    finally:
        app.dependency_overrides.clear()
