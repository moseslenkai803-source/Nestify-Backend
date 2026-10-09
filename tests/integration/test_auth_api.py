from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.landlord import Landlord
from app.models.user import User

client = TestClient(app)


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as test_client:
        yield test_client


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


def test_login_success(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        registration_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "StrongPassword123!",
                "display_name": "Login Landlord",
                "phone": "+254700000000",
            },
        )

        assert registration_response.status_code == 201

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "StrongPassword123!",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert "access_token" in data
        assert data["access_token"]
        assert data["token_type"] == "bearer"

    finally:
        app.dependency_overrides.clear()


def test_login_rejects_wrong_password(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        registration_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong-password@example.com",
                "password": "CorrectPassword123!",
                "display_name": "Test Landlord",
                "phone": "+254711111111",
            },
        )

        assert registration_response.status_code == 201

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong-password@example.com",
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    finally:
        app.dependency_overrides.clear()


def test_login_rejects_unknown_email(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "does-not-exist@example.com",
                "password": "SomePassword123!",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    finally:
        app.dependency_overrides.clear()


def test_register_landlord_rolls_back_user_when_landlord_creation_fails(
    db_session,
    monkeypatch,
):
    def transactional_db():
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise
        else:
            db_session.commit()

    app.dependency_overrides[get_db] = transactional_db

    try:
        from app.services.registration_service import RegistrationService

        original_add = RegistrationService.__init__

        def failing_init(self, db):
            original_add(self, db)

            def failing_landlord_add(landlord):
                raise ValueError("Simulated landlord creation failure")

            self.landlord_repository.add = failing_landlord_add

        monkeypatch.setattr(
            RegistrationService,
            "__init__",
            failing_init,
        )

        email = "rollback@example.com"

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "password123",
                "display_name": "Rollback Landlord",
                "phone": "0712345678",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Simulated landlord creation failure"
        )

        user = (
            db_session.query(User)
            .filter(User.email == email)
            .first()
        )

        assert user is None

    finally:
        app.dependency_overrides.clear()

def test_get_me_returns_authenticated_employee(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        employee = User(
            email=f"employee-me-{uuid4()}@example.com",
            password_hash="not-used",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        token = create_access_token(subject=str(employee.id))

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(employee.id)
        assert data["email"] == employee.email
        assert data["role"] == "employee"
        assert data["clearance"] == "plate_operations"
        assert data["is_active"] is True
        assert "password_hash" not in data

    finally:
        app.dependency_overrides.clear()


def test_get_me_rejects_missing_token(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    finally:
        app.dependency_overrides.clear()


def test_get_me_rejects_invalid_token(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.clear()


def test_get_me_rejects_inactive_user(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        employee = User(
            email=f"inactive-me-{uuid4()}@example.com",
            password_hash="not-used",
            role="employee",
            clearance="plate_operations",
            is_active=False,
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        token = create_access_token(subject=str(employee.id))

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "User account is inactive"

    finally:
        app.dependency_overrides.clear()


def test_get_me_returns_landlord_identity(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        landlord = User(
            email=f"landlord-me-{uuid4()}@example.com",
            password_hash="not-used",
            role="landlord",
            clearance=None,
            is_active=True,
        )
        db_session.add(landlord)
        db_session.commit()
        db_session.refresh(landlord)

        token = create_access_token(subject=str(landlord.id))

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(landlord.id)
        assert data["email"] == landlord.email
        assert data["role"] == "landlord"
        assert data["clearance"] is None
        assert data["is_active"] is True

    finally:
        app.dependency_overrides.clear()


def test_get_me_returns_only_active_employee_clearances(db_session):

    app.dependency_overrides[get_db] = lambda: db_session

    try:
        user = User(
            email=f"employee-permissions-{uuid4()}@example.com",
            password_hash="not-used",
            role="employee",
            clearance="legacy_clearance",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

        employee = Employee(
            user_id=user.id,
            employee_number=f"EMP-{uuid4()}",
            department="Operations",
            position="Officer",
        )
        db_session.add(employee)
        db_session.flush()

        db_session.add_all([
            EmployeeClearance(
                employee_id=employee.id,
                clearance="plate_operations",
                is_active=True,
            ),
            EmployeeClearance(
                employee_id=employee.id,
                clearance="property_verification",
                is_active=False,
            ),
            EmployeeClearance(
                employee_id=employee.id,
                clearance="contractor_management",
                is_active=True,
            ),
        ])
        db_session.commit()

        token = create_access_token(subject=str(user.id))
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["permissions"] == [
            "contractor_management",
            "plate_operations",
        ]
        assert data["clearance"] == "legacy_clearance"

    finally:
        app.dependency_overrides.clear()


def test_get_me_returns_no_permissions_for_ended_employee(db_session):
    from datetime import UTC, datetime

    app.dependency_overrides[get_db] = lambda: db_session

    try:
        user = User(
            email=f"ended-employee-{uuid4()}@example.com",
            password_hash="not-used",
            role="employee",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

        employee = Employee(
            user_id=user.id,
            employee_number=f"EMP-{uuid4()}",
            department="Operations",
            position="Officer",
            ended_at=datetime.now(UTC),
        )
        db_session.add(employee)
        db_session.flush()

        db_session.add(EmployeeClearance(
            employee_id=employee.id,
            clearance="plate_operations",
            is_active=True,
        ))
        db_session.commit()

        token = create_access_token(subject=str(user.id))
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["permissions"] == []

    finally:
        app.dependency_overrides.clear()


def test_get_me_returns_admin_permission(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        admin = User(
            email=f"admin-permissions-{uuid4()}@example.com",
            password_hash="not-used",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()

        token = create_access_token(subject=str(admin.id))
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["permissions"] == ["admin"]

    finally:
        app.dependency_overrides.clear()


def test_get_me_returns_empty_permissions_for_landlord(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        landlord = User(
            email=f"landlord-permissions-{uuid4()}@example.com",
            password_hash="not-used",
            role="landlord",
            is_active=True,
        )
        db_session.add(landlord)
        db_session.commit()

        token = create_access_token(subject=str(landlord.id))
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["permissions"] == []

    finally:
        app.dependency_overrides.clear()
