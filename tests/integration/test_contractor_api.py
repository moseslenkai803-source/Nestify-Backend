import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.user import User


def create_employee_access_token(
    db_session,
    *,
    clearance: str = "contractor_management",
):
    employee = User(
        email=f"contractor-api-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance=clearance,
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return employee.id, create_access_token(
        subject=str(employee.id),
    )


def create_user(db_session, *, role: str = "landlord", is_active: bool = True):
    user = User(
        email=f"contractor-user-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )

    db_session.add(user)
    db_session.flush()

    return user


def test_create_contractor_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        employee_id, access_token = create_employee_access_token(
            db_session
        )

        response = client.post(
            "/api/v1/contractors",
            json={
                "name": "Acme Installations",
                "contractor_type": "company",
                "contact_email": "ops@acme.example",
                "contact_phone": "+254700000000",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["name"] == "Acme Installations"
        assert data["contractor_type"] == "company"
        assert data["status"] == "active"
        assert data["contact_email"] == "ops@acme.example"
        assert data["contact_phone"] == "+254700000000"

        contractor = (
            db_session.query(Contractor)
            .filter(
                Contractor.id == data["id"],
            )
            .one()
        )

        assert contractor.name == "Acme Installations"
        assert contractor.status == "active"

        # Confirm the employee was created and used for authentication.
        assert employee_id is not None

    finally:
        app.dependency_overrides.clear()


def test_create_contractor_api_requires_contractor_management_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session,
            clearance="support",
        )

        response = client.post(
            "/api/v1/contractors",
            json={
                "name": "Restricted Contractor",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_contractor_api_rejects_non_employee(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        user = create_user(
            db_session,
            role="landlord",
        )

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            "/api/v1/contractors",
            json={
                "name": "Restricted Contractor",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Employee access required"
        )

    finally:
        app.dependency_overrides.clear()



def test_list_contractors_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        first = Contractor(
            name="First Contractor",
            contractor_type="company",
            status="active",
        )
        second = Contractor(
            name="Second Contractor",
            contractor_type="company",
            status="inactive",
        )

        db_session.add_all([first, second])
        db_session.flush()

        response = client.get(
            "/api/v1/contractors",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        contractors_by_id = {
            item["id"]: item
            for item in data
        }

        assert str(first.id) in contractors_by_id
        assert str(second.id) in contractors_by_id
        assert contractors_by_id[str(first.id)]["status"] == "active"
        assert contractors_by_id[str(second.id)]["status"] == "inactive"

    finally:
        app.dependency_overrides.clear()


def test_list_contractors_api_active_only(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        active = Contractor(
            name="Active Contractor",
            contractor_type="company",
            status="active",
        )
        inactive = Contractor(
            name="Inactive Contractor",
            contractor_type="company",
            status="inactive",
        )

        db_session.add_all([active, inactive])
        db_session.flush()

        response = client.get(
            "/api/v1/contractors?active_only=true",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        returned_ids = {item["id"] for item in data}

        assert str(active.id) in returned_ids
        assert str(inactive.id) not in returned_ids
        assert all(item["status"] == "active" for item in data)

    finally:
        app.dependency_overrides.clear()


def test_list_contractors_api_requires_contractor_management_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session,
            clearance="property_verification",
        )

        response = client.get(
            "/api/v1/contractors",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_contractor_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Existing Contractor",
            contractor_type="company",
            status="active",
        )

        db_session.add(contractor)
        db_session.flush()

        response = client.get(
            f"/api/v1/contractors/{contractor.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(contractor.id)
        assert data["name"] == "Existing Contractor"
        assert data["contractor_type"] == "company"
        assert data["status"] == "active"

    finally:
        app.dependency_overrides.clear()


def test_get_contractor_api_returns_404_for_missing_contractor(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        response = client.get(
            f"/api/v1/contractors/{uuid.uuid4()}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Contractor not found"

    finally:
        app.dependency_overrides.clear()


def test_add_contractor_member_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Installation Partner",
            contractor_type="company",
            status="active",
        )

        member = create_user(
            db_session,
            role="contractor",
        )

        db_session.add(contractor)
        db_session.flush()

        response = client.post(
            f"/api/v1/contractors/{contractor.id}/members",
            json={
                "user_id": str(member.id),
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["contractor_id"] == str(contractor.id)
        assert data["user_id"] == str(member.id)
        assert data["is_active"] is True

        membership = (
            db_session.query(ContractorMember)
            .filter(
                ContractorMember.contractor_id == contractor.id,
                ContractorMember.user_id == member.id,
            )
            .one()
        )

        assert membership.is_active is True

    finally:
        app.dependency_overrides.clear()


def test_add_contractor_member_api_rejects_non_contractor_user(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Installation Partner",
            contractor_type="company",
            status="active",
        )

        employee = create_user(
            db_session,
            role="employee",
        )

        db_session.add(contractor)
        db_session.flush()

        response = client.post(
            f"/api/v1/contractors/{contractor.id}/members",
            json={
                "user_id": str(employee.id),
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Only contractor users can be contractor members"
        )

    finally:
        app.dependency_overrides.clear()


def test_list_contractor_members_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Installation Partner",
            contractor_type="company",
            status="active",
        )

        member = create_user(
            db_session,
            role="contractor",
        )

        db_session.add(contractor)
        db_session.flush()

        membership = ContractorMember(
            contractor_id=contractor.id,
            user_id=member.id,
            is_active=True,
        )

        db_session.add(membership)
        db_session.flush()

        response = client.get(
            f"/api/v1/contractors/{contractor.id}/members",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["id"] == str(membership.id)
        assert data[0]["contractor_id"] == str(contractor.id)
        assert data[0]["user_id"] == str(member.id)
        assert data[0]["is_active"] is True

    finally:
        app.dependency_overrides.clear()


def test_deactivate_contractor_member_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Installation Partner",
            contractor_type="company",
            status="active",
        )

        member = create_user(
            db_session,
            role="contractor",
        )

        db_session.add(contractor)
        db_session.flush()

        membership = ContractorMember(
            contractor_id=contractor.id,
            user_id=member.id,
            is_active=True,
        )

        db_session.add(membership)
        db_session.flush()

        response = client.post(
            f"/api/v1/contractors/{contractor.id}/members/{member.id}/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(membership.id)
        assert data["is_active"] is False

        db_session.refresh(membership)

        assert membership.is_active is False

    finally:
        app.dependency_overrides.clear()


def test_deactivate_contractor_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Installation Partner",
            contractor_type="company",
            status="active",
        )

        db_session.add(contractor)
        db_session.flush()

        response = client.post(
            f"/api/v1/contractors/{contractor.id}/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(contractor.id)
        assert data["status"] == "inactive"

        db_session.refresh(contractor)

        assert contractor.status == "inactive"

    finally:
        app.dependency_overrides.clear()


def test_deactivate_contractor_api_returns_404_for_missing_contractor(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        response = client.post(
            f"/api/v1/contractors/{uuid.uuid4()}/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Contractor not found"

    finally:
        app.dependency_overrides.clear()


def test_deactivate_contractor_api_rejects_already_inactive_contractor(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Inactive Contractor",
            contractor_type="company",
            status="inactive",
        )

        db_session.add(contractor)
        db_session.flush()

        response = client.post(
            f"/api/v1/contractors/{contractor.id}/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Contractor is already inactive"
        )

    finally:
        app.dependency_overrides.clear()


def test_list_contractor_candidates_returns_safe_active_contractor_users(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor_user = create_user(
            db_session,
            role="contractor",
            is_active=True,
        )
        inactive_contractor = create_user(
            db_session,
            role="contractor",
            is_active=False,
        )
        employee_user = create_user(
            db_session,
            role="employee",
            is_active=True,
        )

        response = client.get(
            "/api/v1/contractors/candidates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        candidate_ids = {candidate["id"] for candidate in data}

        assert str(contractor_user.id) in candidate_ids
        assert str(inactive_contractor.id) not in candidate_ids
        assert str(employee_user.id) not in candidate_ids

        assert all(
            set(candidate.keys()) == {"id", "email"}
            for candidate in data
        )

    finally:
        app.dependency_overrides.clear()


def test_list_contractor_candidates_allows_existing_contractor_members(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        contractor = Contractor(
            name="Existing Contractor",
            contractor_type="company",
            status="active",
        )
        contractor_user = create_user(
            db_session,
            role="contractor",
            is_active=True,
        )

        db_session.add(contractor)
        db_session.flush()

        db_session.add(
            ContractorMember(
                contractor_id=contractor.id,
                user_id=contractor_user.id,
                is_active=True,
            )
        )
        db_session.flush()

        response = client.get(
            "/api/v1/contractors/candidates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()
        candidate_ids = {candidate["id"] for candidate in data}

        assert str(contractor_user.id) in candidate_ids

    finally:
        app.dependency_overrides.clear()


def test_list_contractor_candidates_requires_contractor_management_clearance(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session,
            clearance="support",
        )

        response = client.get(
            "/api/v1/contractors/candidates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_list_contractor_candidates_requires_authentication(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        response = client.get(
            "/api/v1/contractors/candidates",
        )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.clear()


def test_candidates_route_is_not_captured_by_contractor_id(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        _, access_token = create_employee_access_token(
            db_session
        )

        response = client.get(
            "/api/v1/contractors/candidates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

    finally:
        app.dependency_overrides.clear()
