import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.db.session import get_db
from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.user import User
from app.services.property_access_service import PropertyAccessService


def test_activate_property_api(db_session):
        user = User(
                email=f"activation-api-{uuid.uuid4()}@example.com",
                password_hash="test-hash",
                role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
                user_id=user.id,
                display_name="Activation API Landlord",
                phone="+254700000000",
                landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
                landlord_id=landlord.id,
                property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
                name="Activation API Property",
                property_type="residential",
                status="verified",
        )
        db_session.add(property)
        db_session.flush()

        address = PropertyAddress(
                property_id=property.id,
                formatted_address="Activation API Address",
                county="Nairobi",
                locality="Nairobi",
        )
        db_session.add(address)
        db_session.flush()

        plate = AddressPlate(
                plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
                status="verified",
        )
        db_session.add(plate)
        db_session.flush()

        def override_get_db():
                yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
                client = TestClient(app)

                employee = User(
                    email=f"activation-employee-{uuid.uuid4()}@example.com",
                    password_hash="test-hash",
                    role="employee",
                    clearance="plate_operations",
                )
                db_session.add(employee)
                db_session.flush()

                PropertyAccessService(db_session).grant_access(
                    user_id=employee.id,
                    property_id=property.id,
                    access_type="plate_operations",
                )

                access_token = create_access_token(
                    subject=str(employee.id),
                )

                response = client.post(
                        f"/api/v1/properties/{property.id}/activate",
                        headers={
                                "Authorization": f"Bearer {access_token}",
                        },
                        json={
                                "plate_code": plate.plate_code,
                        },
                )

                assert response.status_code == 200

                data = response.json()

                assert data["property_id"] == str(property.id)
                assert data["plate_code"] == plate.plate_code
                assert data["status"] == "active"
                assert data["activated_at"] is not None

                assert property.status == "active"

        finally:
                app.dependency_overrides.clear()


def test_activate_property_api_allows_employee_across_landlord_ownership(
    db_session,
):
    owner_user = User(
        email=f"activation-owner-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(owner_user)
    db_session.flush()

    owner_landlord = Landlord(
        user_id=owner_user.id,
        display_name="Activation Owner",
        phone="+254700000001",
        landlord_type="individual",
    )
    db_session.add(owner_landlord)
    db_session.flush()

    property = Property(
        landlord_id=owner_landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Employee Activation Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Employee Activation Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="verified",
    )
    db_session.add(plate)
    db_session.flush()

    employee = User(
        email=f"activation-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
    )
    db_session.add(employee)
    db_session.flush()

    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "active"
        assert plate.property_id == property.id
        assert plate.status == "active"

    finally:
        app.dependency_overrides.clear()


def test_activate_property_api_requires_property_access(db_session):
    owner_user = User(
        email=f"activation-access-owner-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(owner_user)
    db_session.flush()

    landlord = Landlord(
        user_id=owner_user.id,
        display_name="Activation Access Owner",
        phone="+254700000002",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Unauthorized Activation Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Unauthorized Activation Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="verified",
    )
    db_session.add(plate)
    db_session.flush()

    employee = User(
        email=f"activation-unauthorized-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
    )
    db_session.add(employee)
    db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Employee does not have access to this property"
        )

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "verified"
        assert plate.property_id is None
        assert plate.status == "verified"
        assert plate.activated_at is None

    finally:
        app.dependency_overrides.clear()


def test_activate_property_api_requires_address(db_session):
        user = User(
                email=f"activation-no-address-{uuid.uuid4()}@example.com",
                password_hash="test-hash",
                role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
                user_id=user.id,
                display_name="No Address Landlord",
                phone="+254700000000",
                landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
                landlord_id=landlord.id,
                property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
                name="No Address Property",
                property_type="residential",
                status="verified",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
                plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
                status="verified",
        )
        db_session.add(plate)
        db_session.flush()

        def override_get_db():
                yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
                client = TestClient(app)

                employee = User(
                    email=f"activation-employee-{uuid.uuid4()}@example.com",
                    password_hash="test-hash",
                    role="employee",
                    clearance="plate_operations",
                )
                db_session.add(employee)
                db_session.flush()

                PropertyAccessService(db_session).grant_access(
                    user_id=employee.id,
                    property_id=property.id,
                    access_type="plate_operations",
                )

                access_token = create_access_token(
                    subject=str(employee.id),
                )

                response = client.post(
                        f"/api/v1/properties/{property.id}/activate",
                        headers={
                                "Authorization": f"Bearer {access_token}",
                        },
                        json={
                                "plate_code": plate.plate_code,
                        },
                )

                assert response.status_code == 400
                assert response.json()["detail"] == (
                        "Property must have an address before activation"
                )

                assert property.status == "verified"

        finally:
                app.dependency_overrides.clear()


def test_activate_property_api_returns_404_for_missing_plate(
    db_session,
):
    user = User(
        email=f"activation-missing-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Missing Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Missing Plate Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Missing Plate Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"activation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": "PLATE-DOES-NOT-EXIST",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Plate not found"

        db_session.refresh(property)

        assert property.status == "verified"

    finally:
        app.dependency_overrides.clear()


def test_activate_property_api_rejects_unverified_plate(
    db_session,
):
    user = User(
        email=f"activation-unverified-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Unverified Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Unverified Plate Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Unverified Plate Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"activation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Only verified plates can be linked to a property"
        )

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "verified"
        assert plate.property_id is None
        assert plate.status == "unactivated"
        assert plate.activated_at is None

    finally:
        app.dependency_overrides.clear()


def test_activate_property_api_rejects_already_active_plate(
    db_session,
):
    user = User(
        email=f"activation-active-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Active Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Already Active Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Already Active Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="verified",
    )
    db_session.add(plate)
    db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"activation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        first_response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert first_response.status_code == 200

        second_response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert second_response.status_code == 400
        assert second_response.json()["detail"] == (
            "Property is already active"
        )

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "active"
        assert plate.property_id == property.id
        assert plate.status == "active"
        assert plate.activated_at is not None

    finally:
        app.dependency_overrides.clear()
