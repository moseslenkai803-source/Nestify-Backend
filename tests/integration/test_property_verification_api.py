import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.property_verification import PropertyVerification
from app.models.user import User
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.services.property_access_service import PropertyAccessService


def create_property_verification_fixture(
    db_session: Session,
    *,
    add_address: bool = True,
    grant_access: bool = True,
):
    owner_user = User(
        id=uuid.uuid4(),
        email=f"verification-api-owner-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(owner_user)
    db_session.flush()

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=owner_user.id,
        display_name="Verification API Owner",
        phone="+254700000030",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Verification API Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()

    reviewer = User(
        id=uuid.uuid4(),
        email=f"verification-api-reviewer-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=True,
    )
    db_session.add(reviewer)
    db_session.flush()

    employee_record = Employee(
        user_id=reviewer.id,
        employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
        department="Operations",
        position="Test Employee",
    )
    db_session.add(employee_record)
    db_session.flush()

    db_session.add(
        EmployeeClearance(
            employee_id=employee_record.id,
            clearance="property_verification",
            is_active=True,
        )
    )
    db_session.flush()

    if grant_access:
        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property_record.id,
            access_type="property_verification",
        )

    if add_address:
        address = PropertyAddress(
            id=uuid.uuid4(),
            property_id=property_record.id,
            formatted_address="123 Verification Avenue, Nairobi, Kenya",
            county="Nairobi",
            sub_county="Westlands",
            locality="Nairobi",
        )
        db_session.add(address)
        db_session.flush()

    return property_record, reviewer


def test_verify_property_api(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        property_record, reviewer = create_property_verification_fixture(
            db_session
        )

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property_record.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
                "notes": "Property information verified.",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["property_id"] == str(property_record.id)
        assert data["verified_by"] == str(reviewer.id)
        assert data["status"] == "verified"
        assert data["notes"] == "Property information verified."
        assert data["verified_at"] is not None
        assert data["created_at"] is not None

        db_session.refresh(property_record)

        assert property_record.status == "verified"

        verification = db_session.get(
            PropertyVerification,
            uuid.UUID(data["id"]),
        )

        assert verification is not None
        assert verification.property_id == property_record.id
        assert verification.verified_by == reviewer.id
        assert verification.status == "verified"
        assert verification.notes == "Property information verified."

    finally:
        app.dependency_overrides.clear()


def test_reject_property_api_preserves_property_status(
    db_session: Session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        property_record, reviewer = create_property_verification_fixture(
            db_session
        )

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property_record.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "rejected",
                "notes": "Additional property information required.",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["property_id"] == str(property_record.id)
        assert data["verified_by"] == str(reviewer.id)
        assert data["status"] == "rejected"
        assert data["notes"] == "Additional property information required."

        db_session.refresh(property_record)

        assert property_record.status == "draft"

        verification = db_session.get(
            PropertyVerification,
            uuid.UUID(data["id"]),
        )

        assert verification is not None
        assert verification.status == "rejected"

    finally:
        app.dependency_overrides.clear()


def test_verify_property_api_denies_employee_without_property_access(
    db_session: Session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        property_record, reviewer = create_property_verification_fixture(
            db_session,
            grant_access=False,
        )

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property_record.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_verify_property_api_requires_address(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        property_record, reviewer = create_property_verification_fixture(
            db_session,
            add_address=False,
        )

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property_record.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Property must have an address before verification"
        )

    finally:
        app.dependency_overrides.clear()


def test_verify_property_api_rejects_invalid_status(
    db_session: Session,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        property_record, reviewer = create_property_verification_fixture(
            db_session
        )

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property_record.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "pending",
            },
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()
