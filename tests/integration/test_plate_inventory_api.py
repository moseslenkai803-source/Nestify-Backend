import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)


def create_employee(
    db_session,
    *,
    clearance="plate_operations",
):
    employee = User(
        email=f"plate-inventory-api-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance=clearance,
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee


def create_landlord(db_session):
    user = User(
        email=f"plate-inventory-landlord-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Inventory API Landlord",
        phone=f"+2547{uuid.uuid4().int % 10**8:08d}",
    )

    db_session.add(landlord)
    db_session.flush()

    return landlord


def create_property(db_session, landlord):
    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Inventory API Property",
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


def record_lifecycle(db_session, plate, employee, event_type):
    service = AddressPlateLifecycleService(db_session)

    return service.record_event(
        plate_id=plate.id,
        event_type=event_type,
        performed_by=employee.id,
    )


def test_list_plate_inventory_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee = create_employee(db_session)
        landlord = create_landlord(db_session)
        property_record = create_property(db_session, landlord)

        unassigned_plate = create_plate(db_session)
        assigned_plate = create_plate(
            db_session,
            property_id=property_record.id,
        )

        record_lifecycle(
            db_session,
            unassigned_plate,
            employee,
            "manufactured",
        )

        record_lifecycle(
            db_session,
            assigned_plate,
            employee,
            "manufactured",
        )
        record_lifecycle(
            db_session,
            assigned_plate,
            employee,
            "allocated",
        )

        response = client.get(
            "/api/v1/plate-inventory",
            headers={
                "Authorization": (
                    f"Bearer "
                    f"{create_access_token(subject=str(employee.id))}"
                ),
            },
        )

        assert response.status_code == 200

        data = response.json()

        assigned_record = next(
            record
            for record in data
            if record["id"] == str(assigned_plate.id)
        )
        unassigned_record = next(
            record
            for record in data
            if record["id"] == str(unassigned_plate.id)
        )

        assert assigned_record == {
            "id": str(assigned_plate.id),
            "plate_code": assigned_plate.plate_code,
            "property_id": str(property_record.id),
            "property_code": property_record.property_code,
            "property_name": property_record.name,
            "status": "unactivated",
            "lifecycle_status": "allocated",
            "activated_at": None,
        }

        assert unassigned_record["property_id"] is None
        assert unassigned_record["property_code"] is None
        assert unassigned_record["property_name"] is None
        assert unassigned_record["lifecycle_status"] == "manufactured"

    finally:
        app.dependency_overrides.clear()


def test_list_plate_inventory_api_requires_plate_operations_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee = create_employee(
            db_session,
            clearance="support",
        )

        response = client.get(
            "/api/v1/plate-inventory",
            headers={
                "Authorization": (
                    f"Bearer "
                    f"{create_access_token(subject=str(employee.id))}"
                ),
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_list_plate_inventory_api_requires_authentication(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        response = client.get(
            "/api/v1/plate-inventory",
        )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.clear()
