import uuid

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.landlord import Landlord
from app.models.user import User


def test_create_property_api(db_session):
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

        response = client.post(
            f"/api/v1/properties?landlord_id={landlord.id}",
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


def test_get_property_api(db_session):
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

        create_response = client.post(
            f"/api/v1/properties?landlord_id={landlord.id}",
            json={
                "name": "Retrieval Test Property",
                "property_type": "residential",
            },
        )

        assert create_response.status_code == 201

        property_id = create_response.json()["id"]

        response = client.get(
            f"/api/v1/properties/{property_id}"
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


def test_get_property_api_returns_404_for_missing_property(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        response = client.get(
            f"/api/v1/properties/{uuid.uuid4()}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_list_properties_api_returns_landlord_properties(db_session):
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

        first_response = client.post(
            f"/api/v1/properties?landlord_id={landlord.id}",
            json={
                "name": "First Property",
                "property_type": "residential",
            },
        )

        second_response = client.post(
            f"/api/v1/properties?landlord_id={landlord.id}",
            json={
                "name": "Second Property",
                "property_type": "commercial",
            },
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201

        response = client.get(
            f"/api/v1/properties?landlord_id={landlord.id}"
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2
        assert data[0]["landlord_id"] == str(landlord.id)
        assert data[1]["landlord_id"] == str(landlord.id)

    finally:
        app.dependency_overrides.clear()


def test_list_properties_api_returns_empty_list_for_landlord_with_no_properties(
    db_session,
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

        response = client.get(
            f"/api/v1/properties?landlord_id={landlord.id}"
        )

        assert response.status_code == 200
        assert response.json() == []

    finally:
        app.dependency_overrides.clear()


def test_list_properties_api_returns_404_for_missing_landlord(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        response = client.get(
            f"/api/v1/properties?landlord_id={uuid.uuid4()}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Landlord not found"

    finally:
        app.dependency_overrides.clear()
