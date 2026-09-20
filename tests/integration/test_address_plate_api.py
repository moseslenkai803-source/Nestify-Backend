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
