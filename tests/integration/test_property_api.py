from uuid import UUID
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.user import User
from app.services.property_access_service import PropertyAccessService
from app.services.property_service import PropertyService


def test_create_property_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="API Test Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "name": "API Test Property",
                "property_type": "residential",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["landlord_id"] == str(landlord.id)
        assert data["name"] == "API Test Property"
        assert data["property_type"] == "residential"
        assert data["status"] == "draft"
        assert data["property_code"].startswith("NEST-")

    finally:
        app.dependency_overrides.clear()


def test_create_property_address_api_denies_another_landlord(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"address-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        owner_landlord = Landlord(
            user_id=owner_user.id,
            display_name="Address Owner",
            phone="+254700000001",
            landlord_type="individual",
        )
        db_session.add(owner_landlord)
        db_session.flush()

        property = Property(
            landlord_id=owner_landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Protected Address Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        other_user = User(
            email=f"address-other-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(other_user)
        db_session.flush()

        other_landlord = Landlord(
            user_id=other_user.id,
            display_name="Other Address Landlord",
            phone="+254700000002",
            landlord_type="individual",
        )
        db_session.add(other_landlord)
        db_session.flush()

        other_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/address",
            headers={
                "Authorization": f"Bearer {other_token}",
            },
            json={
                "formatted_address": "Unauthorized Address",
                "county": "Nairobi",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_get_property_address_api_denies_another_landlord(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"address-read-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        owner_landlord = Landlord(
            user_id=owner_user.id,
            display_name="Address Read Owner",
            phone="+254700000001",
            landlord_type="individual",
        )
        db_session.add(owner_landlord)
        db_session.flush()

        property = Property(
            landlord_id=owner_landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Protected Read Address Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        address = PropertyAddress(
            property_id=property.id,
            formatted_address="Private Address, Nairobi",
            county="Nairobi",
            locality="Nairobi",
        )
        db_session.add(address)
        db_session.flush()

        other_user = User(
            email=f"address-read-other-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(other_user)
        db_session.flush()

        other_landlord = Landlord(
            user_id=other_user.id,
            display_name="Other Read Landlord",
            phone="+254700000002",
            landlord_type="individual",
        )
        db_session.add(other_landlord)
        db_session.flush()

        other_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property.id}/address",
            headers={
                "Authorization": f"Bearer {other_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_get_property_address_api_allows_authorized_user(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"address-authorized-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        owner_landlord = Landlord(
            user_id=owner_user.id,
            display_name="Address Authorized Owner",
            phone="+254700000001",
            landlord_type="individual",
        )
        db_session.add(owner_landlord)
        db_session.flush()

        property = Property(
            landlord_id=owner_landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Delegated Address Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        address = PropertyAddress(
            property_id=property.id,
            formatted_address="Delegated Address, Nairobi",
            county="Nairobi",
            locality="Nairobi",
        )
        db_session.add(address)
        db_session.flush()

        authorized_user = User(
            email=f"address-authorized-user-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
        )
        db_session.add(authorized_user)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=authorized_user.id,
            property_id=property.id,
            access_type="property_management",
        )

        access_token = create_access_token(
            subject=str(authorized_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property.id}/address",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["property_id"] == str(property.id)
        assert data["formatted_address"] == "Delegated Address, Nairobi"
        assert data["county"] == "Nairobi"
        assert data["locality"] == "Nairobi"

    finally:
        app.dependency_overrides.clear()


def test_get_property_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"get-api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Get API Test Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        create_response = client.post(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "name": "Retrieval Test Property",
                "property_type": "residential",
            },
        )

        assert create_response.status_code == 201

        property_id = create_response.json()["id"]

        response = client.get(
            f"/api/v1/properties/{property_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == property_id
        assert data["landlord_id"] == str(landlord.id)
        assert data["name"] == "Retrieval Test Property"
        assert data["property_type"] == "residential"
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_get_property_api_denies_access_to_another_landlords_property(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        owner_landlord = Landlord(
            user_id=owner_user.id,
            display_name="Owner Landlord",
            phone="+254700000001",
            landlord_type="individual",
        )
        db_session.add(owner_landlord)
        db_session.flush()

        owner_token = create_access_token(
            subject=str(owner_user.id),
        )

        create_response = client.post(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {owner_token}",
            },
            json={
                "name": "Private Owner Property",
                "property_type": "residential",
            },
        )

        assert create_response.status_code == 201

        property_id = create_response.json()["id"]

        other_user = User(
            email=f"other-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(other_user)
        db_session.flush()

        other_landlord = Landlord(
            user_id=other_user.id,
            display_name="Other Landlord",
            phone="+254700000002",
            landlord_type="individual",
        )
        db_session.add(other_landlord)
        db_session.flush()

        other_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_id}",
            headers={
                "Authorization": f"Bearer {other_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_get_property_api_allows_authorized_user(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"property-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(owner_user)
        db_session.flush()

        owner_landlord = Landlord(
            user_id=owner_user.id,
            display_name="Property Owner",
            phone="+254700000003",
            landlord_type="individual",
        )
        db_session.add(owner_landlord)
        db_session.flush()

        owner_token = create_access_token(
            subject=str(owner_user.id),
        )

        create_response = client.post(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {owner_token}",
            },
            json={
                "name": "Delegated Retrieval Property",
                "property_type": "residential",
            },
        )

        assert create_response.status_code == 201

        property_id = create_response.json()["id"]

        authorized_user = User(
            email=f"property-manager-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
        )
        db_session.add(authorized_user)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=authorized_user.id,
            property_id=UUID(property_id),
            access_type="property_management",
        )

        authorized_token = create_access_token(
            subject=str(authorized_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_id}",
            headers={
                "Authorization": f"Bearer {authorized_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == property_id
        assert data["landlord_id"] == str(owner_landlord.id)
        assert data["name"] == "Delegated Retrieval Property"
        assert data["property_type"] == "residential"

    finally:
        app.dependency_overrides.clear()


def test_get_property_api_returns_404_for_missing_property(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"missing-property-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Missing Property Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{uuid.uuid4()}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_list_properties_api_returns_landlord_properties(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"list-api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="List API Test Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        first_response = client.post(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "name": "First Property",
                "property_type": "residential",
            },
        )

        second_response = client.post(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "name": "Second Property",
                "property_type": "commercial",
            },
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201

        response = client.get(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2
        assert data[0]["landlord_id"] == str(landlord.id)
        assert data[1]["landlord_id"] == str(landlord.id)

    finally:
        app.dependency_overrides.clear()


def test_list_properties_api_returns_empty_list_for_landlord_with_no_properties(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"empty-list-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Empty List Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            "/api/v1/properties",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    finally:
        app.dependency_overrides.clear()


def test_create_property_address_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"address-api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Address API Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        service = PropertyService(db_session)

        property = service.create_property(
            landlord_id=landlord.id,
            name="Address API Property",
            property_type="residential",
        )

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/address",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "formatted_address": "Karen, Nairobi, Kenya",
                "county": "Nairobi",
                "sub_county": "Dagoretti South",
                "locality": "Karen",
                "latitude": -1.3197,
                "longitude": 36.7073,
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["property_id"] == str(property.id)
        assert data["formatted_address"] == "Karen, Nairobi, Kenya"
        assert data["county"] == "Nairobi"
        assert data["sub_county"] == "Dagoretti South"
        assert data["locality"] == "Karen"
        assert data["latitude"] == -1.3197
        assert data["longitude"] == 36.7073

    finally:
        app.dependency_overrides.clear()


def test_get_property_address_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"get-address-api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Get Address API Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        service = PropertyService(db_session)

        property = service.create_property(
            landlord_id=landlord.id,
            name="Get Address Property",
            property_type="residential",
        )

        address = PropertyAddress(
            property_id=property.id,
            formatted_address="Westlands, Nairobi, Kenya",
            county="Nairobi",
            sub_county="Westlands",
            locality="Westlands",
            latitude=-1.2676,
            longitude=36.8108,
        )

        db_session.add(address)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property.id}/address",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["property_id"] == str(property.id)
        assert data["formatted_address"] == "Westlands, Nairobi, Kenya"
        assert data["county"] == "Nairobi"
        assert data["locality"] == "Westlands"

    finally:
        app.dependency_overrides.clear()


def test_get_property_address_api_returns_404_when_missing(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"missing-address-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Missing Address Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        service = PropertyService(db_session)

        property = service.create_property(
            landlord_id=landlord.id,
            name="Missing Address Property",
            property_type="residential",
        )

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property.id}/address",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property address not found"

    finally:
        app.dependency_overrides.clear()


def test_activate_property_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = User(
            email=f"activate-api-{uuid.uuid4()}@example.com",
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

        property_service = PropertyService(db_session)

        property = property_service.create_property(
            landlord_id=landlord.id,
            name="Activation API Property",
            property_type="residential",
        )

        property.status = "verified"
        db_session.flush()

        address = PropertyAddress(
            property_id=property.id,
            formatted_address="Karen, Nairobi, Kenya",
            county="Nairobi",
            sub_county="Dagoretti South",
            locality="Karen",
            latitude=-1.3197,
            longitude=36.7073,
        )
        db_session.add(address)
        db_session.flush()

        from app.services.address_plate_service import AddressPlateService

        plate_service = AddressPlateService(db_session)

        plate = plate_service.create_plate()
        plate_service.verify_plate(plate.plate_code)

        employee = User(
            email=f"activate-employee-{uuid.uuid4()}@example.com",
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

        assert data["id"] == str(plate.id)
        assert data["property_id"] == str(property.id)
        assert data["plate_code"] == plate.plate_code
        assert data["status"] == "active"
        assert data["verified_at"] is not None
        assert data["activated_at"] is not None

        db_session.refresh(property)

        assert property.status == "active"

    finally:
        app.dependency_overrides.clear()
