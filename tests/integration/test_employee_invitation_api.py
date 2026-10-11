import hashlib
from urllib.parse import parse_qs, urlparse
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.employee_invitation import EmployeeInvitation
from app.models.user import User


def make_user(db, role):
    user = User(
        id=uuid.uuid4(),
        email=f"invitation-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def test_admin_can_create_employee_invitation(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        admin = make_user(db_session, "admin")
        token = create_access_token(subject=str(admin.id))
        response = TestClient(app).post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "New.Employee@example.com",
                "employee_number": "INV-001",
                "department": "Operations",
                "position": "Field Officer",
                "clearances": ["plate_operations"],
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["email"] == "new.employee@example.com"
        assert data["employee_number"] == "INV-001"

        invitation_token = parse_qs(
            urlparse(data["invitation_url"]).query
        )["token"][0]
        invitation = db_session.query(EmployeeInvitation).filter_by(
            id=data["id"]
        ).one()

        assert invitation.token_hash == hashlib.sha256(
            invitation_token.encode()
        ).hexdigest()
        assert invitation.token_hash != invitation_token
        assert invitation.redeemed_at is None
    finally:
        app.dependency_overrides.clear()


def test_admin_cannot_create_invitation_with_unsupported_clearance(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        admin = make_user(db_session, "admin")
        token = create_access_token(subject=str(admin.id))
        response = TestClient(app).post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "invalid.clearance@example.com",
                "employee_number": "INV-INVALID",
                "department": "Operations",
                "position": "Field Officer",
                "clearances": ["unknown_permission"],
            },
        )

        assert response.status_code == 400, response.text
    finally:
        app.dependency_overrides.clear()


def test_invitation_acceptance_creates_employee_and_is_one_time(db_session):
    from app.models.employee import Employee
    from app.models.employee_clearance import EmployeeClearance

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    try:
        admin = make_user(db_session, "admin")
        admin_token = create_access_token(subject=str(admin.id))
        created = client.post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "accept.employee@example.com",
                "employee_number": "INV-002",
                "department": "Operations",
                "position": "Verifier",
                "clearances": ["plate_operations", "property_verification"],
            },
        )
        assert created.status_code == 201, created.text
        invite_token = parse_qs(
            urlparse(created.json()["invitation_url"]).query
        )["token"][0]

        accepted = client.post(
            "/api/v1/auth/employee-invitations/accept",
            json={"token": invite_token, "password": "SecurePass123!"},
        )
        assert accepted.status_code == 201, accepted.text
        result = accepted.json()

        employee = db_session.query(Employee).filter_by(
            id=result["employee_id"]
        ).one()
        assert str(employee.user_id) == result["user_id"]
        assert employee.employee_number == "INV-002"

        clearances = db_session.query(EmployeeClearance).filter_by(
            employee_id=employee.id
        ).all()
        assert {item.clearance for item in clearances} == {
            "plate_operations", "property_verification"
        }

        invitation = db_session.query(EmployeeInvitation).filter_by(
            id=created.json()["id"]
        ).one()
        assert invitation.redeemed_at is not None

        reused = client.post(
            "/api/v1/auth/employee-invitations/accept",
            json={"token": invite_token, "password": "AnotherPass123!"},
        )
        assert reused.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_non_admin_cannot_create_employee_invitation(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        employee = make_user(db_session, "employee")
        token = create_access_token(subject=str(employee.id))
        response = TestClient(app).post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "blocked@example.com",
                "employee_number": "INV-003",
                "department": "Operations",
                "position": "Officer",
                "clearances": [],
            },
        )
        assert response.status_code == 403
        assert db_session.query(EmployeeInvitation).filter_by(
            email="blocked@example.com"
        ).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_invalid_invitation_token_does_not_create_user(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post(
            "/api/v1/auth/employee-invitations/accept",
            json={
                "token": "x" * 43,
                "password": "SecurePass123!",
            },
        )
        assert response.status_code == 400
        assert db_session.query(User).filter_by(
            email="nobody@example.com"
        ).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_expired_invitation_is_rejected(db_session):
    from datetime import UTC, datetime, timedelta

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    try:
        admin = make_user(db_session, "admin")
        admin_token = create_access_token(subject=str(admin.id))
        created = client.post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "expired.employee@example.com",
                "employee_number": "INV-004",
                "department": "Operations",
                "position": "Officer",
                "clearances": ["plate_operations"],
            },
        )
        assert created.status_code == 201, created.text
        db_session.commit()
        invite_token = parse_qs(
            urlparse(created.json()["invitation_url"]).query
        )["token"][0]

        invitation = db_session.query(EmployeeInvitation).filter_by(
            id=created.json()["id"]
        ).one()
        invitation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db_session.flush()
        db_session.commit()

        response = client.post(
            "/api/v1/auth/employee-invitations/accept",
            json={"token": invite_token, "password": "SecurePass123!"},
        )
        assert response.status_code == 400
        refreshed_invitation = db_session.query(EmployeeInvitation).filter_by(
            id=created.json()["id"]
        ).one()
        assert refreshed_invitation.redeemed_at is None
        assert db_session.query(User).filter_by(
            email="expired.employee@example.com"
        ).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_invitation_acceptance_rejects_short_password(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post(
            "/api/v1/auth/employee-invitations/accept",
            json={"token": "x" * 43, "password": "short"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_failed_employee_creation_rolls_back_invited_user(db_session, monkeypatch):
    from app.services.employee_service import EmployeeService

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    email = f"rollback-{uuid.uuid4()}@example.com"
    try:
        admin = make_user(db_session, "admin")
        admin_token = create_access_token(subject=str(admin.id))
        created = client.post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": email,
                "employee_number": f"INV-{uuid.uuid4().hex[:12]}",
                "department": "Operations",
                "position": "Officer",
                "clearances": ["plate_operations"],
            },
        )
        assert created.status_code == 201, created.text
        db_session.commit()
        invite_token = parse_qs(
            urlparse(created.json()["invitation_url"]).query
        )["token"][0]

        def fail_employee_creation(self, **kwargs):
            raise ValueError("Simulated employee creation failure")

        monkeypatch.setattr(
            EmployeeService, "create_employee", fail_employee_creation
        )
        response = client.post(
            "/api/v1/auth/employee-invitations/accept",
            json={"token": invite_token, "password": "SecurePass123!"},
        )

        assert response.status_code == 400
        assert db_session.query(User).filter_by(email=email).count() == 0

        invitation = db_session.query(EmployeeInvitation).filter_by(
            id=created.json()["id"]
        ).one()
        assert invitation.redeemed_at is None
    finally:
        app.dependency_overrides.clear()


def test_invitation_creation_blocked_outside_development(db_session, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    app.dependency_overrides[get_db] = lambda: db_session
    email = f"blocked-{uuid.uuid4()}@example.com"
    try:
        admin = make_user(db_session, "admin")
        token = create_access_token(subject=str(admin.id))
        response = TestClient(app).post(
            "/api/v1/employees/invitations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": email,
                "employee_number": f"INV-{uuid.uuid4().hex[:12]}",
                "department": "Operations",
                "position": "Officer",
                "clearances": ["plate_operations"],
            },
        )
        assert response.status_code == 503, response.text
        assert db_session.query(EmployeeInvitation).filter_by(email=email).count() == 0
    finally:
        app.dependency_overrides.clear()
