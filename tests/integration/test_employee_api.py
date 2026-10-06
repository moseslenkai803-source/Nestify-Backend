import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.user import User


def create_user(
    db_session,
    *,
    role: str,
    is_active: bool = True,
):
    user = User(
        id=uuid.uuid4(),
        email=f"employee-api-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )

    db_session.add(user)
    db_session.flush()

    return user


def create_access_token_for_user(user):
    return create_access_token(
        subject=str(user.id),
    )


def test_create_employee_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        access_token = create_access_token_for_user(admin)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(employee_user.id),
                "employee_number": "EMP-API-001",
                "department": "Operations",
                "position": "Field Officer",
                "clearances": [
                    "plate_operations",
                    "property_verification",
                ],
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["user_id"] == str(employee_user.id)
        assert data["employee_number"] == "EMP-API-001"
        assert data["department"] == "Operations"
        assert data["position"] == "Field Officer"
        assert data["ended_at"] is None
        assert data["joined_at"] is not None

        employee = (
            db_session.query(Employee)
            .filter(Employee.id == data["id"])
            .one()
        )

        assert employee.user_id == employee_user.id

        clearances = (
            db_session.query(EmployeeClearance)
            .filter(
                EmployeeClearance.employee_id == employee.id,
            )
            .order_by(EmployeeClearance.clearance)
            .all()
        )

        assert [item.clearance for item in clearances] == [
            "plate_operations",
            "property_verification",
        ]

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_rejects_non_admin(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee = create_user(
            db_session,
            role="employee",
        )

        target_user = create_user(
            db_session,
            role="employee",
        )

        access_token = create_access_token_for_user(employee)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(target_user.id),
                "employee_number": "EMP-API-002",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_rejects_landlord(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        landlord = create_user(
            db_session,
            role="landlord",
        )

        target_user = create_user(
            db_session,
            role="employee",
        )

        access_token = create_access_token_for_user(landlord)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(target_user.id),
                "employee_number": "EMP-API-003",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_rejects_contractor(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        contractor = create_user(
            db_session,
            role="contractor",
        )

        target_user = create_user(
            db_session,
            role="employee",
        )

        access_token = create_access_token_for_user(contractor)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(target_user.id),
                "employee_number": "EMP-API-004",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_rejects_inactive_admin(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
            is_active=False,
        )

        target_user = create_user(
            db_session,
            role="employee",
        )

        access_token = create_access_token_for_user(admin)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(target_user.id),
                "employee_number": "EMP-API-005",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "User account is inactive"

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_requires_authentication(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        target_user = create_user(
            db_session,
            role="employee",
        )

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(target_user.id),
                "employee_number": "EMP-API-006",
                "department": "Operations",
                "position": "Officer",
            },
        )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_rejects_missing_user(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        access_token = create_access_token_for_user(admin)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(uuid.uuid4()),
                "employee_number": "EMP-API-007",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "User not found"

    finally:
        app.dependency_overrides.clear()


def test_create_employee_api_rejects_non_employee_target_user(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        landlord = create_user(
            db_session,
            role="landlord",
        )

        access_token = create_access_token_for_user(admin)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(landlord.id),
                "employee_number": "EMP-API-008",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Only employee users can have employee records"
        )

    finally:
        app.dependency_overrides.clear()


def test_list_employees_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        first_user = create_user(
            db_session,
            role="employee",
        )

        second_user = create_user(
            db_session,
            role="employee",
        )

        first = Employee(
            user_id=first_user.id,
            employee_number="EMP-API-LIST-001",
            department="Operations",
            position="Officer",
        )

        second = Employee(
            user_id=second_user.id,
            employee_number="EMP-API-LIST-002",
            department="Verification",
            position="Verifier",
        )

        db_session.add_all([first, second])
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.get(
            "/api/v1/employees",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        returned_ids = {item["id"] for item in data}

        assert str(first.id) in returned_ids
        assert str(second.id) in returned_ids

    finally:
        app.dependency_overrides.clear()


def test_list_active_employees_api_excludes_terminated_employee(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        active_user = create_user(
            db_session,
            role="employee",
        )

        terminated_user = create_user(
            db_session,
            role="employee",
        )

        active_employee = Employee(
            user_id=active_user.id,
            employee_number="EMP-API-ACTIVE",
            department="Operations",
            position="Officer",
        )

        terminated_employee = Employee(
            user_id=terminated_user.id,
            employee_number="EMP-API-ENDED",
            department="Operations",
            position="Officer",
        )

        from datetime import UTC, datetime

        terminated_employee.ended_at = datetime.now(UTC)

        db_session.add_all(
            [
                active_employee,
                terminated_employee,
            ]
        )
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.get(
            "/api/v1/employees?active_only=true",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        returned_ids = {item["id"] for item in data}

        assert str(active_employee.id) in returned_ids
        assert str(terminated_employee.id) not in returned_ids

    finally:
        app.dependency_overrides.clear()


def test_get_employee_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-GET",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.get(
            f"/api/v1/employees/{employee.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(employee.id)
        assert data["user_id"] == str(employee_user.id)
        assert data["employee_number"] == "EMP-API-GET"

    finally:
        app.dependency_overrides.clear()


def test_get_employee_api_returns_404_for_missing_employee(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        access_token = create_access_token_for_user(admin)

        employee_id = uuid.uuid4()

        response = client.get(
            f"/api/v1/employees/{employee_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"

    finally:
        app.dependency_overrides.clear()


def test_add_employee_clearance_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-CLEAR-001",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.post(
            f"/api/v1/employees/{employee.id}/clearances",
            json={
                "clearance": "plate_operations",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["employee_id"] == str(employee.id)
        assert data["clearance"] == "plate_operations"
        assert data["is_active"] is True

        record = (
            db_session.query(EmployeeClearance)
            .filter(EmployeeClearance.id == data["id"])
            .one()
        )

        assert record.is_active is True

    finally:
        app.dependency_overrides.clear()


def test_list_employee_clearances_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-CLEAR-002",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        first = EmployeeClearance(
            employee_id=employee.id,
            clearance="plate_operations",
            is_active=True,
        )

        second = EmployeeClearance(
            employee_id=employee.id,
            clearance="property_verification",
            is_active=False,
        )

        db_session.add_all([first, second])
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.get(
            f"/api/v1/employees/{employee.id}/clearances",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        returned = {
            item["clearance"]: item["is_active"]
            for item in data
        }

        assert returned == {
            "plate_operations": True,
            "property_verification": False,
        }

    finally:
        app.dependency_overrides.clear()


def test_list_active_employee_clearances_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-CLEAR-003",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        active = EmployeeClearance(
            employee_id=employee.id,
            clearance="plate_operations",
            is_active=True,
        )

        inactive = EmployeeClearance(
            employee_id=employee.id,
            clearance="property_verification",
            is_active=False,
        )

        db_session.add_all([active, inactive])
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.get(
            f"/api/v1/employees/{employee.id}/clearances?active_only=true",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["clearance"] == "plate_operations"
        assert data[0]["is_active"] is True

    finally:
        app.dependency_overrides.clear()


def test_remove_employee_clearance_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-CLEAR-004",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        clearance = EmployeeClearance(
            employee_id=employee.id,
            clearance="plate_operations",
            is_active=True,
        )

        db_session.add(clearance)
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.post(
            f"/api/v1/employees/{employee.id}/clearances/"
            f"{clearance.clearance}/remove",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(clearance.id)
        assert data["is_active"] is False

        db_session.refresh(clearance)

        assert clearance.is_active is False

    finally:
        app.dependency_overrides.clear()


def test_reactivate_employee_clearance_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-CLEAR-005",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        clearance = EmployeeClearance(
            employee_id=employee.id,
            clearance="plate_operations",
            is_active=False,
        )

        db_session.add(clearance)
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.post(
            f"/api/v1/employees/{employee.id}/clearances",
            json={
                "clearance": "plate_operations",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] == str(clearance.id)
        assert data["is_active"] is True

        db_session.refresh(clearance)

        assert clearance.is_active is True

    finally:
        app.dependency_overrides.clear()


def test_remove_employee_clearance_api_returns_404_for_missing_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-CLEAR-006",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.post(
            f"/api/v1/employees/{employee.id}/clearances/"
            "plate_operations/remove",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Active employee clearance not found"
        )

    finally:
        app.dependency_overrides.clear()


def test_employee_clearance_api_returns_404_for_missing_employee(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        access_token = create_access_token_for_user(admin)

        employee_id = uuid.uuid4()

        response = client.post(
            f"/api/v1/employees/{employee_id}/clearances",
            json={
                "clearance": "plate_operations",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"

    finally:
        app.dependency_overrides.clear()


def test_terminate_employee_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-TERM-001",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        first = EmployeeClearance(
            employee_id=employee.id,
            clearance="plate_operations",
            is_active=True,
        )

        second = EmployeeClearance(
            employee_id=employee.id,
            clearance="property_verification",
            is_active=True,
        )

        db_session.add_all([first, second])
        db_session.flush()

        access_token = create_access_token_for_user(admin)

        response = client.post(
            f"/api/v1/employees/{employee.id}/terminate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(employee.id)
        assert data["ended_at"] is not None

        db_session.refresh(employee)
        db_session.refresh(employee_user)
        db_session.refresh(first)
        db_session.refresh(second)

        assert employee.ended_at is not None
        assert employee_user.is_active is False
        assert first.is_active is False
        assert second.is_active is False

    finally:
        app.dependency_overrides.clear()


def test_terminate_employee_api_returns_404_for_missing_employee(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        access_token = create_access_token_for_user(admin)

        response = client.post(
            f"/api/v1/employees/{uuid.uuid4()}/terminate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"

    finally:
        app.dependency_overrides.clear()


def test_terminate_employee_api_rejects_already_terminated_employee(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-TERM-002",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        first_response = client.post(
            f"/api/v1/employees/{employee.id}/terminate",
            headers={
                "Authorization": (
                    f"Bearer {create_access_token_for_user(admin)}"
                ),
            },
        )

        second_response = client.post(
            f"/api/v1/employees/{employee.id}/terminate",
            headers={
                "Authorization": (
                    f"Bearer {create_access_token_for_user(admin)}"
                ),
            },
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 400
        assert second_response.json()["detail"] == (
            "Employee is already terminated"
        )

    finally:
        app.dependency_overrides.clear()


def test_terminated_employee_api_cannot_receive_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        employee_user = create_user(
            db_session,
            role="employee",
        )

        employee = Employee(
            user_id=employee_user.id,
            employee_number="EMP-API-TERM-003",
            department="Operations",
            position="Officer",
        )

        db_session.add(employee)
        db_session.flush()

        terminate_response = client.post(
            f"/api/v1/employees/{employee.id}/terminate",
            headers={
                "Authorization": (
                    f"Bearer {create_access_token_for_user(admin)}"
                ),
            },
        )

        assert terminate_response.status_code == 200

        response = client.post(
            f"/api/v1/employees/{employee.id}/clearances",
            json={
                "clearance": "plate_operations",
            },
            headers={
                "Authorization": (
                    f"Bearer {create_access_token_for_user(admin)}"
                ),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Employee is terminated"

    finally:
        app.dependency_overrides.clear()


def test_employee_api_rejects_invalid_create_payload(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        admin = create_user(
            db_session,
            role="admin",
        )

        access_token = create_access_token_for_user(admin)

        response = client.post(
            "/api/v1/employees",
            json={
                "user_id": str(uuid.uuid4()),
                "employee_number": "",
                "department": "Operations",
                "position": "Officer",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()
