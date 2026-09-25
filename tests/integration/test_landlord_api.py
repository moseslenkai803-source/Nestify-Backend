import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.services.user_service import UserService
from app.services.registration_service import RegistrationService

client = TestClient(app)


def test_onboard_landlord_route_success(db_session):
    # 1. Arrange: Instantiate user account context
    user_service = UserService(db_session)
    email = f"onboard-api-{uuid.uuid4()}@example.com"
    user = user_service.create_user(email=email, password="password123", role="customer")
    
    # Override dependencies: Inject active user session context directly
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # 2. Act: Send structural onboarding requests via test engine client
        response = client.post(
            "/api/v1/landlords/onboard",
            json={
                "display_name": "API Onboarded Landlord",
                "phone": "+254799000000",
                "landlord_type": "individual"
            }
        )
        
        # 3. Assert: Verify operational HTTP status and body fields
        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "API Onboarded Landlord"
        assert data["phone"] == "+254799000000"
        assert data["landlord_type"] == "individual"
        assert data["user_id"] == str(user.id)
        assert "id" in data
        
    finally:
        app.dependency_overrides.clear()


def test_onboard_landlord_fails_if_already_landlord(db_session):
    # 1. Arrange: Seed a user profile who is already onboarded
    email = f"already-api-{uuid.uuid4()}@example.com"
    reg_service = RegistrationService(db_session)
    user, _ = reg_service.register_landlord(
        email=email,
        password="password123",
        display_name="Existing Profile Holder",
        phone="+254799111111"
    )
    
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # 2. Act: Submit duplicate onboarding parameters
        response = client.post(
            "/api/v1/landlords/onboard",
            json={
                "display_name": "Fraudulent Second Profile",
                "phone": "+254799222222"
            }
        )
        
        # 3. Assert: Ensure baseline throws standard 400 bad request error payload
        assert response.status_code == 400
        assert "already registered as a landlord" in response.json()["detail"]
        
    finally:
        app.dependency_overrides.clear()


def test_onboard_landlord_validation_error(db_session):
    # Arrange: Setup basic authenticated context boundary hooks
    user_service = UserService(db_session)
    user = user_service.create_user(email=f"val-{uuid.uuid4()}@example.com", password="password123")
    
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # Act: Pass incomplete input components (omitting required phone payload data)
        response = client.post(
            "/api/v1/landlords/onboard",
            json={
                "display_name": "Incomplete Payload Model"
            }
        )
        
        # Assert: Pydantic should natively capture type layout validation failures
        assert response.status_code == 422
        
    finally:
        app.dependency_overrides.clear()
