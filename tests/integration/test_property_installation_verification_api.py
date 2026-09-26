from datetime import UTC, datetime
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import AddressPlateLifecycleEvent
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_installation import PropertyInstallation
from app.models.property_installation_verification import (
    PropertyInstallationVerification,
)
from app.models.user import User
from app.services.property_access_service import PropertyAccessService


def test_verify_property_installation_api(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"verification-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Verification Owner",
            phone="+254700000010",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Verification Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"verification-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        for event_type in ("manufactured", "allocated", "dispatched"):
            db_session.add(
                AddressPlateLifecycleEvent(
                    plate_id=plate.id,
                    event_type=event_type,
                    performed_by=reviewer.id,
                )
            )
        db_session.flush()


        captured_at = datetime(
            2026,
            9,
            23,
            10,
            30,
            tzinfo=UTC,
        )

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=4.5,
            captured_at=captured_at,
            status="submitted",
            notes="Plate installed and GPS captured on site.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(
            subject=str(reviewer.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "status": "verified",
                "notes": "Installation evidence confirmed.",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["installation_id"] == str(installation.id)
        assert data["verified_by"] == str(reviewer.id)
        assert data["status"] == "verified"
        assert data["notes"] == "Installation evidence confirmed."
        assert data["verified_at"] is not None
        assert data["created_at"] is not None

        db_session.refresh(installation)

        assert installation.status == "verified"

        verification = db_session.get(
            PropertyInstallationVerification,
            uuid.UUID(data["id"]),
        )

        assert verification is not None
        assert verification.installation_id == installation.id
        assert verification.verified_by == reviewer.id
        assert verification.status == "verified"
        assert verification.notes == "Installation evidence confirmed."

    finally:
        app.dependency_overrides.clear()



def test_reject_property_installation_api(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"rejection-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Rejection Owner",
            phone="+254700000011",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Rejection Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"rejection-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
            status="submitted",
            notes="Installation submitted for review.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "rejected",
                "notes": "Installation evidence requires correction.",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["installation_id"] == str(installation.id)
        assert data["verified_by"] == str(reviewer.id)
        assert data["status"] == "rejected"
        assert data["notes"] == "Installation evidence requires correction."

        db_session.refresh(installation)
        assert installation.status == "rejected"

        verification = db_session.get(
            PropertyInstallationVerification,
            uuid.UUID(data["id"]),
        )

        assert verification is not None
        assert verification.status == "rejected"
        assert verification.verified_by == reviewer.id

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_denies_user_without_property_access(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"access-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Access Owner",
            phone="+254700000012",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Access Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"access-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 11, 30, tzinfo=UTC),
            status="submitted",
            notes="Awaiting verification.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
                "notes": "Unauthorized verification attempt.",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "User is not authorized for this property"

        db_session.refresh(installation)
        assert installation.status == "submitted"

        verifications = db_session.query(
            PropertyInstallationVerification
        ).filter(
            PropertyInstallationVerification.installation_id == installation.id
        ).all()

        assert verifications == []

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_denies_wrong_clearance(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"clearance-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Clearance Owner",
            phone="+254700000013",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Clearance Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"clearance-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
            status="submitted",
            notes="Awaiting verification.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
                "notes": "Should not be accepted.",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient employee clearance"

        db_session.refresh(installation)
        assert installation.status == "submitted"

        verifications = db_session.query(
            PropertyInstallationVerification
        ).filter(
            PropertyInstallationVerification.installation_id == installation.id
        ).all()

        assert verifications == []

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_denies_non_employee(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"role-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Role Owner",
            phone="+254700000014",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Role Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"role-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 12, 30, tzinfo=UTC),
            status="submitted",
            notes="Awaiting verification.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
                "notes": "Should not be accepted.",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Employee access required"

        db_session.refresh(installation)
        assert installation.status == "submitted"

        verifications = db_session.query(
            PropertyInstallationVerification
        ).filter(
            PropertyInstallationVerification.installation_id == installation.id
        ).all()

        assert verifications == []

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_missing_property(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        reviewer = User(
            email=f"missing-property-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        missing_property_id = uuid.uuid4()
        installation_id = uuid.uuid4()
        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{missing_property_id}/installations/"
            f"{installation_id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"status": "verified", "notes": "Should not be accepted."},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_missing_installation(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"missing-installation-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Missing Installation Owner",
            phone="+254700000015",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Missing Installation Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"missing-installation-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        access_token = create_access_token(subject=str(reviewer.id))
        missing_installation_id = uuid.uuid4()

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{missing_installation_id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"status": "verified", "notes": "Should not be accepted."},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Installation not found"

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_rejects_wrong_property(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_one_user = User(
            email=f"wrong-property-owner-one-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        owner_two_user = User(
            email=f"wrong-property-owner-two-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add_all([owner_one_user, owner_two_user])
        db_session.flush()

        landlord_one = Landlord(
            user_id=owner_one_user.id,
            display_name="Wrong Property Owner One",
            phone="+254700000016",
            landlord_type="individual",
        )
        landlord_two = Landlord(
            user_id=owner_two_user.id,
            display_name="Wrong Property Owner Two",
            phone="+254700000017",
            landlord_type="individual",
        )
        db_session.add_all([landlord_one, landlord_two])
        db_session.flush()

        property_one = Property(
            landlord_id=landlord_one.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Authorized Property",
            property_type="residential",
            status="verified",
        )
        property_two = Property(
            landlord_id=landlord_two.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Installation Property",
            property_type="residential",
            status="verified",
        )
        db_session.add_all([property_one, property_two])
        db_session.flush()

        reviewer = User(
            email=f"wrong-property-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property_one.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property_two.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property_two.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 13, 0, tzinfo=UTC),
            status="submitted",
            notes="Installation belongs to another property.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property_one.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "verified",
                "notes": "Should not be accepted.",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Installation does not belong to this property"

        db_session.refresh(installation)
        assert installation.status == "submitted"

        verifications = db_session.query(
            PropertyInstallationVerification
        ).filter(
            PropertyInstallationVerification.installation_id == installation.id
        ).all()

        assert verifications == []

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_rejects_already_verified(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"already-verified-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Already Verified Owner",
            phone="+254700000018",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Already Verified Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"already-verified-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 13, 30, tzinfo=UTC),
            status="verified",
            notes="Already verified installation.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "rejected",
                "notes": "Should not change an already verified installation.",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Installation is not awaiting verification"

        db_session.refresh(installation)
        assert installation.status == "verified"

        verifications = db_session.query(
            PropertyInstallationVerification
        ).filter(
            PropertyInstallationVerification.installation_id == installation.id
        ).all()

        assert verifications == []

    finally:
        app.dependency_overrides.clear()



def test_verify_property_installation_api_rejects_invalid_status(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"invalid-status-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Invalid Status Owner",
            phone="+254700000019",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Invalid Status Test Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        reviewer = User(
            email=f"invalid-status-reviewer-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="installation_verification",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        PropertyAccessService(db_session).grant_access(
            user_id=reviewer.id,
            property_id=property.id,
            access_type="installation_verification",
        )

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="active",
        )
        db_session.add(plate)
        db_session.flush()

        installation = PropertyInstallation(
            property_id=property.id,
            plate_id=plate.id,
            installer_id=reviewer.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 13, 30, tzinfo=UTC),
            status="submitted",
            notes="Awaiting verification.",
        )
        db_session.add(installation)
        db_session.flush()

        access_token = create_access_token(subject=str(reviewer.id))

        response = client.post(
            f"/api/v1/properties/{property.id}/installations/"
            f"{installation.id}/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "status": "pending",
                "notes": "Invalid status should be rejected by the API schema.",
            },
        )

        assert response.status_code == 422

        db_session.refresh(installation)
        assert installation.status == "submitted"

        verifications = db_session.query(
            PropertyInstallationVerification
        ).filter(
            PropertyInstallationVerification.installation_id == installation.id
        ).all()

        assert verifications == []

    finally:
        app.dependency_overrides.clear()
