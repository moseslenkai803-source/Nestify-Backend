import uuid

from fastapi.testclient import TestClient
import pytest

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User


def create_plate_operations_employee(db_session):
    employee = User(
        email=f"plate-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return create_access_token(
        subject=str(employee.id),
    )


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

        access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

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


def create_plate_operations_employee_with_id(db_session):
    employee = User(
        email=f"plate-employee-access-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee.id, create_access_token(
        subject=str(employee.id),
    )


def create_user_access_token(
    db_session,
    *,
    role: str,
    clearance: str | None = None,
):
    user = User(
        email=f"auth-test-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        clearance=clearance,
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    return create_access_token(
        subject=str(user.id),
    )


@pytest.mark.parametrize(
    ("role", "clearance", "expected_detail"),
    [
        ("landlord", "plate_operations", "Employee access required"),
        ("employee", None, "Insufficient employee clearance"),
        ("employee", "support", "Insufficient employee clearance"),
    ],
)
def test_create_address_plate_api_requires_employee_clearance(
    db_session,
    role,
    clearance,
    expected_detail,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        access_token = create_user_access_token(
            db_session,
            role=role,
            clearance=clearance,
        )

        response = TestClient(app).post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == expected_detail

    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("role", "clearance", "expected_detail"),
    [
        ("landlord", "plate_operations", "Employee access required"),
        ("employee", None, "Insufficient employee clearance"),
        ("employee", "support", "Insufficient employee clearance"),
    ],
)
def test_verify_address_plate_api_requires_employee_clearance(
    client,
    db_session,
    role,
    clearance,
    expected_detail,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        from app.services.address_plate_service import AddressPlateService

        service = AddressPlateService(db_session)
        plate = service.create_plate()

        restricted_token = create_user_access_token(
            db_session,
            role=role,
            clearance=clearance,
        )

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/verify",
            headers={
                "Authorization": f"Bearer {restricted_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == expected_detail

        db_session.refresh(plate)

        assert plate.status == "unactivated"
        assert plate.verified_at is None

    finally:
        app.dependency_overrides.clear()




def test_get_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        access_token = create_plate_operations_employee(
            db_session
        )

        create_response = client.post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

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

        access_token = create_plate_operations_employee(
            db_session
        )

        create_response = client.post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        plate_code = create_response.json()["plate_code"]

        response = client.post(
            f"/api/v1/address-plates/{plate_code}/verify",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate_code
        assert data["status"] == "verified"
        assert data["verified_at"] is not None
        assert data["activated_at"] is None

    finally:
        app.dependency_overrides.clear()
















