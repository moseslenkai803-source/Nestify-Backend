import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import (
    AddressPlateLifecycleEvent,
)
from app.models.address_plate_request import AddressPlateRequest
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.property_access_service import PropertyAccessService


def create_user(
    db_session,
    *,
    role: str,
    clearance: str | None = None,
):
    user = User(
        email=f"allocation-api-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        clearance=clearance,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    return user


def create_landlord_and_property(db_session):
    user = create_user(
        db_session,
        role="landlord",
    )

    landlord = Landlord(
        user_id=user.id,
        display_name="Allocation API Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Allocation API Test Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    return user, property


def create_manufactured_plate(
    db_session,
    *,
    performed_by,
):
    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    event = AddressPlateLifecycleEvent(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=performed_by,
    )
    db_session.add(event)
    db_session.flush()

    return plate


def create_approved_request(
    db_session,
    *,
    property_id,
    requested_by,
):
    request = AddressPlateRequest(
        property_id=property_id,
        requested_by=requested_by,
        status="approved",
    )
    db_session.add(request)
    db_session.flush()

    return request


@pytest.fixture(name="client")
def client_fixture(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_allocate_address_plate_api_success(
    client,
    db_session,
):
    landlord_user, property = create_landlord_and_property(
        db_session,
    )

    employee = create_user(
        db_session,
        role="employee",
        clearance="plate_operations",
    )

    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    request = create_approved_request(
        db_session,
        property_id=property.id,
        requested_by=landlord_user.id,
    )

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "verified"},
        synchronize_session="fetch",
    )

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "verified"},
        synchronize_session="fetch",
    )

    plate = create_manufactured_plate(
        db_session,
        performed_by=employee.id,
    )

    access_token = create_access_token(
        subject=str(employee.id),
    )

    response = client.post(
        f"/api/v1/address-plate-requests/{request.id}/allocate",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(plate.id)
    assert data["property_id"] == str(property.id)
    assert data["plate_code"] == plate.plate_code
    assert data["status"] == "unactivated"
    assert data["activated_at"] is None
    assert data["verified_at"] is None

    db_session.refresh(request)
    db_session.refresh(plate)

    assert request.status == "fulfilled"
    assert plate.property_id == property.id
    assert plate.status == "unactivated"

    event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
            AddressPlateLifecycleEvent.event_type == "allocated",
        )
        .first()
    )

    assert event is not None
    assert event.performed_by == employee.id


def test_allocate_address_plate_api_requires_property_access(
    client,
    db_session,
):
    landlord_user, property = create_landlord_and_property(
        db_session,
    )

    employee = create_user(
        db_session,
        role="employee",
        clearance="plate_operations",
    )

    request = create_approved_request(
        db_session,
        property_id=property.id,
        requested_by=landlord_user.id,
    )

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "verified"},
        synchronize_session="fetch",
    )

    plate = create_manufactured_plate(
        db_session,
        performed_by=employee.id,
    )

    access_token = create_access_token(
        subject=str(employee.id),
    )

    response = client.post(
        f"/api/v1/address-plate-requests/{request.id}/allocate",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Employee does not have access to this property"
    )

    db_session.refresh(request)
    db_session.refresh(plate)

    assert request.status == "approved"
    assert plate.property_id is None


@pytest.mark.parametrize(
    ("role", "clearance", "expected_detail"),
    [
        (
            "landlord",
            "plate_operations",
            "Employee access required",
        ),
        (
            "employee",
            None,
            "Insufficient employee clearance",
        ),
        (
            "employee",
            "support",
            "Insufficient employee clearance",
        ),
    ],
)
def test_allocate_address_plate_api_requires_employee_clearance(
    client,
    db_session,
    role,
    clearance,
    expected_detail,
):
    landlord_user, property = create_landlord_and_property(
        db_session,
    )

    request = create_approved_request(
        db_session,
        property_id=property.id,
        requested_by=landlord_user.id,
    )

    employee = create_user(
        db_session,
        role="employee",
        clearance="plate_operations",
    )

    create_manufactured_plate(
        db_session,
        performed_by=employee.id,
    )

    restricted_user = create_user(
        db_session,
        role=role,
        clearance=clearance,
    )

    access_token = create_access_token(
        subject=str(restricted_user.id),
    )

    response = client.post(
        f"/api/v1/address-plate-requests/{request.id}/allocate",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == expected_detail


def test_allocate_address_plate_api_rejects_missing_request(
    client,
    db_session,
):
    employee = create_user(
        db_session,
        role="employee",
        clearance="plate_operations",
    )

    access_token = create_access_token(
        subject=str(employee.id),
    )

    request_id = uuid.uuid4()

    response = client.post(
        f"/api/v1/address-plate-requests/{request_id}/allocate",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Address plate request not found"
    )


def test_allocate_address_plate_api_rejects_when_inventory_is_empty(
    client,
    db_session,
):
    landlord_user, property = create_landlord_and_property(
        db_session,
    )

    employee = create_user(
        db_session,
        role="employee",
        clearance="plate_operations",
    )

    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    request = create_approved_request(
        db_session,
        property_id=property.id,
        requested_by=landlord_user.id,
    )


    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "verified"},
        synchronize_session="fetch",
    )

    access_token = create_access_token(
        subject=str(employee.id),
    )

    response = client.post(
        f"/api/v1/address-plate-requests/{request.id}/allocate",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "No address plates available for allocation"
    )

    db_session.refresh(request)
    assert request.status == "approved"


def test_allocate_address_plate_api_preserves_unactivated_status(
    client,
    db_session,
):
    landlord_user, property = create_landlord_and_property(
        db_session,
    )

    employee = create_user(
        db_session,
        role="employee",
        clearance="plate_operations",
    )

    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    request = create_approved_request(
        db_session,
        property_id=property.id,
        requested_by=landlord_user.id,
    )

    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "verified"},
        synchronize_session="fetch",
    )

    plate = create_manufactured_plate(
        db_session,
        performed_by=employee.id,
    )

    access_token = create_access_token(
        subject=str(employee.id),
    )

    response = client.post(
        f"/api/v1/address-plate-requests/{request.id}/allocate",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200

    db_session.refresh(plate)

    assert plate.status == "unactivated"
    assert plate.activated_at is None
    assert plate.property_id == property.id
