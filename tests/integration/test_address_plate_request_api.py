import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate_request import AddressPlateRequest
from app.models.landlord import Landlord
from app.models.user import User
from app.services.property_service import PropertyService


def test_create_address_plate_request_api(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"plate-request-api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Plate Request API Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Plate Request API Property",
            property_type="residential",
        )

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/address-plate-requests",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["property_id"] == str(property.id)
        assert data["requested_by"] == str(user.id)
        assert data["status"] == "pending"
        assert data["requested_at"] is not None
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

        request = (
            db_session.query(AddressPlateRequest)
            .filter(
                AddressPlateRequest.id == data["id"],
            )
            .one()
        )

        assert request.property_id == property.id
        assert request.requested_by == user.id
        assert request.status == "pending"

    finally:
        app.dependency_overrides.clear()

def test_create_address_plate_request_api_denies_unauthorized_user(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"plate-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Plate Owner",
            phone="+254700000001",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Protected Plate Property",
            property_type="residential",
        )

        unauthorized_user = User(
            email=f"unauthorized-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(unauthorized_user)
        db_session.flush()

        access_token = create_access_token(
            subject=str(unauthorized_user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/address-plate-requests",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_address_plate_request_api_rejects_duplicate_pending_request(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"duplicate-plate-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Duplicate Plate Request Landlord",
            phone="+254700000002",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Duplicate Request Property",
            property_type="residential",
        )

        access_token = create_access_token(
            subject=str(user.id),
        )

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        first_response = client.post(
            f"/api/v1/properties/{property.id}/address-plate-requests",
            headers=headers,
        )

        assert first_response.status_code == 201

        second_response = client.post(
            f"/api/v1/properties/{property.id}/address-plate-requests",
            headers=headers,
        )

        assert second_response.status_code == 400
        assert second_response.json()["detail"] == (
            "Property already has a pending address plate request"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_address_plate_request_api_rejects_property_with_active_plate(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"active-plate-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Active Plate Landlord",
            phone="+254700000003",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Active Plate Property",
            property_type="residential",
        )

        from app.models.address_plate import AddressPlate

        active_plate = AddressPlate(
            property_id=property.id,
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            status="active",
        )
        db_session.add(active_plate)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/address-plate-requests",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Property already has an active address plate"
        )

    finally:
        app.dependency_overrides.clear()


def create_plate_operations_employee(db_session: Session):
    employee = User(
        email=f"plate-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee, create_access_token(
        subject=str(employee.id),
    )


def test_approve_address_plate_request_api(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"approve-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Approve Request Landlord",
            phone="+254700000010",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Approve Request Property",
            property_type="residential",
        )

        request = AddressPlateRequest(
            property_id=property.id,
            requested_by=owner.id,
            status="pending",
        )
        db_session.add(request)
        db_session.flush()

        employee, access_token = create_plate_operations_employee(
            db_session,
        )

        response = client.post(
            f"/api/v1/address-plate-requests/{request.id}/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(request.id)
        assert data["property_id"] == str(property.id)
        assert data["requested_by"] == str(owner.id)
        assert data["status"] == "approved"

        db_session.refresh(request)

        assert request.status == "approved"

    finally:
        app.dependency_overrides.clear()


def test_reject_address_plate_request_api(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"reject-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Reject Request Landlord",
            phone="+254700000011",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Reject Request Property",
            property_type="residential",
        )

        request = AddressPlateRequest(
            property_id=property.id,
            requested_by=owner.id,
            status="pending",
        )
        db_session.add(request)
        db_session.flush()

        employee, access_token = create_plate_operations_employee(
            db_session,
        )

        response = client.post(
            f"/api/v1/address-plate-requests/{request.id}/reject",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(request.id)
        assert data["property_id"] == str(property.id)
        assert data["requested_by"] == str(owner.id)
        assert data["status"] == "rejected"

        db_session.refresh(request)

        assert request.status == "rejected"

    finally:
        app.dependency_overrides.clear()


def test_approve_address_plate_request_api_denies_non_employee(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"approve-denied-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Approve Denied Landlord",
            phone="+254700000012",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Approve Denied Property",
            property_type="residential",
        )

        request = AddressPlateRequest(
            property_id=property.id,
            requested_by=owner.id,
            status="pending",
        )
        db_session.add(request)
        db_session.flush()

        access_token = create_access_token(
            subject=str(owner.id),
        )

        response = client.post(
            f"/api/v1/address-plate-requests/{request.id}/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Employee access required"

        db_session.refresh(request)

        assert request.status == "pending"

    finally:
        app.dependency_overrides.clear()


def test_reject_address_plate_request_api_denies_non_employee(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"reject-denied-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Reject Denied Landlord",
            phone="+254700000013",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Reject Denied Property",
            property_type="residential",
        )

        request = AddressPlateRequest(
            property_id=property.id,
            requested_by=owner.id,
            status="pending",
        )
        db_session.add(request)
        db_session.flush()

        access_token = create_access_token(
            subject=str(owner.id),
        )

        response = client.post(
            f"/api/v1/address-plate-requests/{request.id}/reject",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Employee access required"

        db_session.refresh(request)

        assert request.status == "pending"

    finally:
        app.dependency_overrides.clear()


def test_approve_address_plate_request_api_returns_404_for_missing_request(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee, access_token = create_plate_operations_employee(
            db_session,
        )

        missing_request_id = uuid.uuid4()

        response = client.post(
            f"/api/v1/address-plate-requests/{missing_request_id}/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Address plate request not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_approve_address_plate_request_api_rejects_already_approved_request(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"double-approve-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Double Approve Landlord",
            phone="+254700000014",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Double Approve Property",
            property_type="residential",
        )

        request = AddressPlateRequest(
            property_id=property.id,
            requested_by=owner.id,
            status="approved",
        )
        db_session.add(request)
        db_session.flush()

        employee, access_token = create_plate_operations_employee(
            db_session,
        )

        response = client.post(
            f"/api/v1/address-plate-requests/{request.id}/approve",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Address plate request is not pending"
        )

        db_session.refresh(request)

        assert request.status == "approved"

    finally:
        app.dependency_overrides.clear()


def test_reject_address_plate_request_api_rejects_already_approved_request(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = User(
            email=f"reject-approved-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner)
        db_session.flush()

        landlord = Landlord(
            user_id=owner.id,
            display_name="Reject Approved Landlord",
            phone="+254700000015",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Reject Approved Property",
            property_type="residential",
        )

        request = AddressPlateRequest(
            property_id=property.id,
            requested_by=owner.id,
            status="approved",
        )
        db_session.add(request)
        db_session.flush()

        employee, access_token = create_plate_operations_employee(
            db_session,
        )

        response = client.post(
            f"/api/v1/address-plate-requests/{request.id}/reject",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Address plate request is not pending"
        )

        db_session.refresh(request)

        assert request.status == "approved"

    finally:
        app.dependency_overrides.clear()
