from datetime import UTC, datetime
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_installation import PropertyInstallation
from app.models.user import User
from app.services.property_access_service import PropertyAccessService


def test_create_property_installation_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"installation-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Installation Owner",
            phone="+254700000001",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Installation Test Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"installer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        captured_at = datetime(
            2026,
            9,
            23,
            10,
            30,
            tzinfo=UTC,
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/installations",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_id": str(plate.id),
                "latitude": -1.2921,
                "longitude": 36.8219,
                "accuracy_meters": 4.5,
                "captured_at": captured_at.isoformat(),
                "notes": "Plate installed and GPS captured on site.",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["property_id"] == str(property.id)
        assert data["plate_id"] == str(plate.id)
        assert data["installer_id"] == str(employee.id)
        assert data["latitude"] == -1.2921
        assert data["longitude"] == 36.8219
        assert data["accuracy_meters"] == 4.5
        assert data["status"] == "submitted"
        assert data["notes"] == "Plate installed and GPS captured on site."

        installation = db_session.get(
            PropertyInstallation,
            uuid.UUID(data["id"]),
        )

        assert installation is not None
        assert installation.property_id == property.id
        assert installation.plate_id == plate.id
        assert installation.installer_id == employee.id
        assert installation.status == "submitted"

    finally:
        app.dependency_overrides.clear()


def test_create_property_installation_api_allows_authorized_employee(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"installation-owner-cross-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Cross Owner",
            phone="+254700000002",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Cross Owner Installation Property",
            property_type="office",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"installation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/installations",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "plate_id": str(plate.id),
                "latitude": -1.3000,
                "longitude": 36.8000,
                "accuracy_meters": 3.0,
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 201

    finally:
        app.dependency_overrides.clear()


def test_create_property_installation_api_denies_employee_without_property_access(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"installation-denied-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Denied Owner",
            phone="+254700000003",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Protected Installation Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"installation-denied-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/installations",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "plate_id": str(plate.id),
                "latitude": -1.3000,
                "longitude": 36.8000,
                "accuracy_meters": 3.0,
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_property_installation_api_returns_404_for_missing_property(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"installation-missing-property-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        token = create_access_token(
            subject=str(employee.id),
        )

        missing_property_id = uuid.uuid4()

        response = client.post(
            f"/api/v1/properties/{missing_property_id}/installations",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "plate_id": str(uuid.uuid4()),
                "latitude": -1.3000,
                "longitude": 36.8000,
                "accuracy_meters": 3.0,
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_create_property_installation_api_returns_404_for_missing_plate(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"installation-missing-plate-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Missing Plate Owner",
            phone="+254700000004",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Missing Plate Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"installation-missing-plate-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/installations",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "plate_id": str(uuid.uuid4()),
                "latitude": -1.3000,
                "longitude": 36.8000,
                "accuracy_meters": 3.0,
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Address plate not found"

    finally:
        app.dependency_overrides.clear()


def test_create_property_installation_api_rejects_plate_linked_to_another_property(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"installation-mismatch-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Mismatch Owner",
            phone="+254700000005",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Installation Mismatch Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        other_property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Other Installation Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(other_property)
        db_session.flush()

        employee = User(
            email=f"installation-mismatch-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=other_property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/installations",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "plate_id": str(plate.id),
                "latitude": -1.3000,
                "longitude": 36.8000,
                "accuracy_meters": 3.0,
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Address plate is not linked to this property"
        )

    finally:
        app.dependency_overrides.clear()
