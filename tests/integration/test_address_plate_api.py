import uuid

from fastapi.testclient import TestClient
import pytest

from app.db.session import get_db
from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as test_client:
        yield test_client


def test_create_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        response = client.post("/api/v1/address-plates")

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["property_id"] is None
        assert data["plate_code"].startswith("PLATE-")
        assert data["status"] == "unactivated"
        assert data["activated_at"] is None
        assert data["verified_at"] is None

    finally:
        app.dependency_overrides.clear()


def test_get_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        create_response = client.post(
            "/api/v1/address-plates"
        )

        plate_code = create_response.json()["plate_code"]

        response = client.get(
            f"/api/v1/address-plates/{plate_code}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate_code
        assert data["status"] == "unactivated"

    finally:
        app.dependency_overrides.clear()


def test_get_address_plate_api_returns_404_for_missing_plate(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        response = client.get(
            f"/api/v1/address-plates/PLATE-{uuid.uuid4().hex[:12].upper()}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Plate not found"

    finally:
        app.dependency_overrides.clear()


def test_verify_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        create_response = client.post(
            "/api/v1/address-plates"
        )

        plate_code = create_response.json()["plate_code"]

        response = client.post(
            f"/api/v1/address-plates/{plate_code}/verify"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate_code
        assert data["status"] == "verified"
        assert data["verified_at"] is not None
        assert data["activated_at"] is None

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        email = f"link-api-{uuid.uuid4()}@example.com"
        password = "StrongPassword123!"

        registration_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": "Link API Landlord",
                "phone": "+254700000000",
                "landlord_type": "individual",
            },
        )

        assert registration_response.status_code == 201

        registration_data = registration_response.json()

        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )

        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]

        from app.models.property import Property
        from app.repositories.landlord_repository import LandlordRepository
        from app.services.address_plate_service import AddressPlateService

        landlord_repository = LandlordRepository(db_session)

        landlord = landlord_repository.get_by_id(
            registration_data["landlord_id"]
        )

        assert landlord is not None

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Link API Property",
            property_type="residential",
            status="draft",
        )

        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate.plate_code
        assert data["property_id"] == str(property.id)
        assert data["status"] == "active"
        assert data["verified_at"] is not None
        assert data["activated_at"] is not None

    finally:
        app.dependency_overrides.clear()


def test_link_unverified_address_plate_api(
    client,
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.models.user import User
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        email = f"unverified-link-{uuid.uuid4()}@example.com"
        password = "StrongPassword123!"

        registration_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": "Unverified Link Landlord",
                "phone": "+254700000000",
            },
        )

        assert registration_response.status_code == 201

        landlord_id = registration_response.json()["landlord_id"]

        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )

        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]

        landlord = db_session.get(
            Landlord,
            uuid.UUID(landlord_id),
        )

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Unverified Link Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)
        plate = service.create_plate()

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Only verified plates can be linked to a property"
        )

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_returns_404_for_missing_property(
    client,
    db_session,
):
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        email = f"missing-property-{uuid.uuid4()}@example.com"
        password = "StrongPassword123!"

        registration_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": "Missing Property Landlord",
                "phone": "+254700000000",
            },
        )

        assert registration_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )

        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]

        service = AddressPlateService(db_session)
        plate = service.create_plate()

        service.verify_plate(plate.plate_code)

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_rejects_property_with_existing_plate(
    client,
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        email = f"double-link-{uuid.uuid4()}@example.com"
        password = "StrongPassword123!"

        registration_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": "Double Link Landlord",
                "phone": "+254700000000",
            },
        )

        assert registration_response.status_code == 201

        landlord_id = registration_response.json()["landlord_id"]

        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )

        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]

        landlord = db_session.get(
            Landlord,
            uuid.UUID(landlord_id),
        )

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Double Link Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        first_plate = service.create_plate()
        service.verify_plate(first_plate.plate_code)

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        first_response = client.post(
            f"/api/v1/address-plates/{first_plate.plate_code}/link",
            headers=headers,
            json={
                "property_id": str(property.id),
            },
        )

        assert first_response.status_code == 200

        second_plate = service.create_plate()
        service.verify_plate(second_plate.plate_code)

        second_response = client.post(
            f"/api/v1/address-plates/{second_plate.plate_code}/link",
            headers=headers,
            json={
                "property_id": str(property.id),
            },
        )

        assert second_response.status_code == 400
        assert second_response.json()["detail"] == (
            "Property already has a primary address plate"
        )

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_requires_authentication(db_session):
    from app.models.landlord import Landlord
    from app.models.user import User
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        user = User(
            email=f"unauth-link-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Unauthenticated Link Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Unauthenticated Link Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        response = TestClient(app).post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code in {401, 403}

        db_session.refresh(plate)

        assert plate.property_id is None
        assert plate.status == "verified"
        assert plate.activated_at is None

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_rejects_property_owned_by_another_landlord(
    client,
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        # Create landlord A through the real authentication flow.
        landlord_a_email = f"landlord-a-{uuid.uuid4()}@example.com"
        landlord_a_password = "StrongPassword123!"

        registration_a = client.post(
            "/api/v1/auth/register",
            json={
                "email": landlord_a_email,
                "password": landlord_a_password,
                "display_name": "Landlord A",
                "phone": "+254700000001",
            },
        )

        assert registration_a.status_code == 201

        landlord_a_id = registration_a.json()["landlord_id"]

        login_a = client.post(
            "/api/v1/auth/login",
            json={
                "email": landlord_a_email,
                "password": landlord_a_password,
            },
        )

        assert login_a.status_code == 200

        token_a = login_a.json()["access_token"]

        # Create landlord B directly for the ownership boundary test.
        from app.models.landlord import Landlord
        from app.models.property import Property
        from app.models.user import User
        from app.services.address_plate_service import AddressPlateService

        user_b = User(
            email=f"landlord-b-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user_b)
        db_session.flush()

        landlord_b = Landlord(
            user_id=user_b.id,
            display_name="Landlord B",
            phone="+254700000002",
            landlord_type="individual",
        )
        db_session.add(landlord_b)
        db_session.flush()

        property_b = Property(
            landlord_id=landlord_b.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Landlord B Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property_b)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
            json={
                "property_id": str(property_b.id),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

        db_session.refresh(plate)

        assert plate.property_id is None
        assert plate.status == "verified"
        assert plate.activated_at is None

        assert landlord_a_id != str(landlord_b.id)

    finally:
        app.dependency_overrides.clear()
