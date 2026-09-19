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
