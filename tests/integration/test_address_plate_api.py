import uuid

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


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


def test_link_address_plate_api(db_session):
    from app.models.landlord import Landlord
    from app.models.user import User
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        user = User(
            email=f"link-api-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Link API Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

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

        response = TestClient(app).post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
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


def test_link_unverified_address_plate_api(db_session):
    from app.models.landlord import Landlord
    from app.models.user import User
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        user = User(
            email=f"unverified-link-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Unverified Link Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

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

        response = TestClient(app).post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
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
    db_session,
):
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        service = AddressPlateService(db_session)
        plate = service.create_plate()

        service.verify_plate(plate.plate_code)

        response = TestClient(app).post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            json={
                "property_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_rejects_property_with_existing_plate(
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.user import User
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        user = User(
            email=f"double-link-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Double Link Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

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

        first_response = TestClient(app).post(
            f"/api/v1/address-plates/{first_plate.plate_code}/link",
            json={
                "property_id": str(property.id),
            },
        )

        assert first_response.status_code == 200

        second_plate = service.create_plate()
        service.verify_plate(second_plate.plate_code)

        second_response = TestClient(app).post(
            f"/api/v1/address-plates/{second_plate.plate_code}/link",
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
