from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.landlord import Landlord
from app.models.user import User

client = TestClient(app)


def test_register_landlord_success(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "api-landlord@example.com",
                "password": "password123",
                "display_name": "API Landlord",
                "phone": "0712345678",
                "landlord_type": "individual",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["email"] == "api-landlord@example.com"
        assert data["display_name"] == "API Landlord"
        assert data["phone"] == "0712345678"
        assert data["landlord_type"] == "individual"

        assert "user_id" in data
        assert "landlord_id" in data

        assert "password" not in data
        assert "password_hash" not in data

    finally:
        app.dependency_overrides.clear()


def test_register_landlord_rejects_invalid_email(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "display_name": "Invalid Email",
                "phone": "0712345678",
            },
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_register_landlord_rejects_missing_required_field(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "missing-field@example.com",
                "password": "password123",
                "display_name": "Missing Phone",
            },
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_register_landlord_rejects_duplicate_email(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        payload = {
            "email": "duplicate@example.com",
            "password": "password123",
            "display_name": "Duplicate Test",
            "phone": "0712345678",
        }

        first_response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        second_response = client.post(
            "/api/v1/auth/register",
            json=payload,
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 400

    finally:
        app.dependency_overrides.clear()


def test_register_landlord_persists_user_and_landlord(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        email = "persisted@example.com"

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "password123",
                "display_name": "Persisted Landlord",
                "phone": "0712345678",
            },
        )

        assert response.status_code == 201

        data = response.json()

        user = (
            db_session.query(User)
            .filter(User.email == email)
            .first()
        )

        assert user is not None

        landlord = (
            db_session.query(Landlord)
            .filter(Landlord.user_id == user.id)
            .first()
        )

        assert landlord is not None

        assert str(user.id) == data["user_id"]
        assert str(landlord.id) == data["landlord_id"]

    finally:
        app.dependency_overrides.clear()
