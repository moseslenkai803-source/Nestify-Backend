import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import AddressPlateLifecycleEvent
from app.models.dispatch_item import DispatchItem
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.user import User


def create_plate_operations_employee(db_session):
    employee = User(
        email=f"dispatch-api-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    employee_record = Employee(
        user_id=employee.id,
        employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
        department="Operations",
        position="Test Employee",
    )
    db_session.add(employee_record)
    db_session.flush()

    employee_clearance = EmployeeClearance(
        employee_id=employee_record.id,
        clearance="plate_operations",
        is_active=True,
    )
    db_session.add(employee_clearance)
    db_session.flush()

    return employee, create_access_token(
        subject=str(employee.id),
    )


def create_user_access_token(
    db_session,
    *,
    role: str,
    clearance: str | None = None,
):
    user = User(
        email=f"dispatch-auth-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    if role == "employee":
        employee_record = Employee(
            user_id=user.id,
            employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
            department="Operations",
            position="Test Employee",
        )
        db_session.add(employee_record)
        db_session.flush()

        if clearance is not None:
            employee_clearance = EmployeeClearance(
                employee_id=employee_record.id,
                clearance=clearance,
                is_active=True,
            )
            db_session.add(employee_clearance)
            db_session.flush()

    return create_access_token(
        subject=str(user.id),
    )


def create_landlord_and_property(db_session):
    user = User(
        email=f"dispatch-landlord-api-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Dispatch API Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )

    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Dispatch API Test Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(property)
    db_session.flush()

    return property


def create_manufactured_allocated_plate(
    db_session,
    property_id,
    employee_id,
):
    plate = AddressPlate(
        property_id=property_id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    db_session.add(
        AddressPlateLifecycleEvent(
            plate_id=plate.id,
            event_type="manufactured",
            performed_by=employee_id,
            notes="Manufactured for dispatch API test",
        )
    )

    db_session.add(
        AddressPlateLifecycleEvent(
            plate_id=plate.id,
            event_type="allocated",
            performed_by=employee_id,
            notes="Allocated for dispatch API test",
        )
    )

    db_session.flush()

    return plate


def test_create_dispatch_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        property = create_landlord_and_property(db_session)

        plate = create_manufactured_allocated_plate(
            db_session,
            property.id,
            employee.id,
        )

        response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
                "tracking_reference": "TRACK-API-001",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["dispatch_code"].startswith("DSP-")
        assert data["status"] == "draft"
        assert data["destination"] == "Nairobi"
        assert data["recipient_name"] == "Jane Doe"
        assert data["recipient_phone"] == "+254711111111"
        assert data["tracking_reference"] == "TRACK-API-001"
        assert data["created_by"] == str(employee.id)
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

        item = (
            db_session.query(DispatchItem)
            .filter(
                DispatchItem.plate_id == plate.id,
            )
            .one()
        )

        assert item.released_at is None

    finally:
        app.dependency_overrides.clear()


def test_dispatch_api_requires_plate_operations_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        access_token = create_user_access_token(
            db_session,
            role="employee",
            clearance="support",
        )

        response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(uuid.uuid4())],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_dispatch_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        property = create_landlord_and_property(db_session)

        plate = create_manufactured_allocated_plate(
            db_session,
            property.id,
            employee.id,
        )

        create_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        dispatch_code = create_response.json()["dispatch_code"]

        response = client.get(
            f"/api/v1/dispatches/{dispatch_code}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["dispatch_code"] == dispatch_code
        assert data["status"] == "draft"
        assert data["created_by"] == str(employee.id)

    finally:
        app.dependency_overrides.clear()


def test_get_dispatch_plates_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        property = create_landlord_and_property(db_session)

        plate = create_manufactured_allocated_plate(
            db_session,
            property.id,
            employee.id,
        )

        create_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        dispatch_code = create_response.json()["dispatch_code"]

        response = client.get(
            f"/api/v1/dispatches/{dispatch_code}/plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["id"] == str(plate.id)
        assert data[0]["property_id"] == str(property.id)
        assert data[0]["plate_code"] == plate.plate_code
        assert data[0]["status"] == "unactivated"

    finally:
        app.dependency_overrides.clear()


def test_get_dispatch_api_returns_404_for_missing_dispatch(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_plate_operations_employee(
            db_session
        )

        response = client.get(
            "/api/v1/dispatches/DSP-DOES-NOT-EXIST",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Dispatch not found"

    finally:
        app.dependency_overrides.clear()


def test_dispatch_api_full_state_flow(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        property = create_landlord_and_property(db_session)

        plate = create_manufactured_allocated_plate(
            db_session,
            property.id,
            employee.id,
        )

        create_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        dispatch_code = create_response.json()["dispatch_code"]

        ready_response = client.post(
            f"/api/v1/dispatches/{dispatch_code}/ready",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert ready_response.status_code == 200
        assert ready_response.json()["status"] == "ready"

        dispatch_response = client.post(
            f"/api/v1/dispatches/{dispatch_code}/dispatch",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert dispatch_response.status_code == 200
        assert dispatch_response.json()["status"] == "dispatched"

        delivered_response = client.post(
            f"/api/v1/dispatches/{dispatch_code}/deliver",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert delivered_response.status_code == 200
        assert delivered_response.json()["status"] == "delivered"

        events = (
            db_session.query(AddressPlateLifecycleEvent)
            .filter(
                AddressPlateLifecycleEvent.plate_id == plate.id,
            )
            .order_by(AddressPlateLifecycleEvent.occurred_at)
            .all()
        )

        assert [event.event_type for event in events] == [
            "manufactured",
            "allocated",
            "dispatched",
        ]

    finally:
        app.dependency_overrides.clear()


def test_dispatch_api_rejects_invalid_transition(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        property = create_landlord_and_property(db_session)

        plate = create_manufactured_allocated_plate(
            db_session,
            property.id,
            employee.id,
        )

        create_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        dispatch_code = create_response.json()["dispatch_code"]

        response = client.post(
            f"/api/v1/dispatches/{dispatch_code}/dispatch",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Dispatch cannot transition to the requested status"
        )

    finally:
        app.dependency_overrides.clear()


def test_cancel_dispatch_api_releases_plate_assignment(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        property = create_landlord_and_property(db_session)

        plate = create_manufactured_allocated_plate(
            db_session,
            property.id,
            employee.id,
        )

        create_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        dispatch_code = create_response.json()["dispatch_code"]

        response = client.post(
            f"/api/v1/dispatches/{dispatch_code}/cancel",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

        item = (
            db_session.query(DispatchItem)
            .filter(
                DispatchItem.plate_id == plate.id,
            )
            .one()
        )

        assert item.released_at is not None

    finally:
        app.dependency_overrides.clear()


def test_create_dispatch_api_rejects_unallocated_plate(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            status="unactivated",
        )

        db_session.add(plate)
        db_session.flush()

        db_session.add(
            AddressPlateLifecycleEvent(
                plate_id=plate.id,
                event_type="manufactured",
                performed_by=employee.id,
            )
        )
        db_session.flush()

        response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Address plate must be allocated to a property before dispatch"
        )

    finally:
        app.dependency_overrides.clear()


def test_list_dispatches_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        first_property = create_landlord_and_property(
            db_session
        )
        second_property = create_landlord_and_property(
            db_session
        )

        first_plate = create_manufactured_allocated_plate(
            db_session,
            first_property.id,
            employee.id,
        )
        second_plate = create_manufactured_allocated_plate(
            db_session,
            second_property.id,
            employee.id,
        )

        first_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(first_plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        second_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(second_plate.id)],
                "destination": "Mombasa",
                "recipient_name": "John Doe",
                "recipient_phone": "+254722222222",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201

        response = client.get(
            "/api/v1/dispatches",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        dispatch_codes = [item["dispatch_code"] for item in data]

        first_code = first_response.json()["dispatch_code"]
        second_code = second_response.json()["dispatch_code"]

        assert second_code in dispatch_codes
        assert first_code in dispatch_codes
        assert dispatch_codes.index(second_code) < dispatch_codes.index(first_code)

        second_item = next(
            item for item in data if item["dispatch_code"] == second_code
        )
        first_item = next(
            item for item in data if item["dispatch_code"] == first_code
        )

        assert second_item["status"] == "draft"
        assert first_item["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_list_dispatches_api_filters_by_status(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session
        )
        first_property = create_landlord_and_property(
            db_session
        )
        second_property = create_landlord_and_property(
            db_session
        )

        first_plate = create_manufactured_allocated_plate(
            db_session,
            first_property.id,
            employee.id,
        )
        second_plate = create_manufactured_allocated_plate(
            db_session,
            second_property.id,
            employee.id,
        )

        first_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(first_plate.id)],
                "destination": "Nairobi",
                "recipient_name": "Jane Doe",
                "recipient_phone": "+254711111111",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        second_response = client.post(
            "/api/v1/dispatches",
            json={
                "plate_ids": [str(second_plate.id)],
                "destination": "Mombasa",
                "recipient_name": "John Doe",
                "recipient_phone": "+254722222222",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201

        first_code = first_response.json()["dispatch_code"]
        second_code = second_response.json()["dispatch_code"]

        ready_response = client.post(
            f"/api/v1/dispatches/{first_code}/ready",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert ready_response.status_code == 200

        response = client.get(
            "/api/v1/dispatches?status=ready",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["dispatch_code"] == first_code
        assert data[0]["status"] == "ready"
        assert data[0]["dispatch_code"] != second_code

    finally:
        app.dependency_overrides.clear()


def test_list_dispatches_api_requires_plate_operations_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        access_token = create_user_access_token(
            db_session,
            role="employee",
            clearance="support",
        )

        response = client.get(
            "/api/v1/dispatches",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()
