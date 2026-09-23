import uuid
from datetime import UTC, datetime

from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_installation import PropertyInstallation
from app.models.property_installation_verification import (
    PropertyInstallationVerification,
)
from app.models.user import User
from app.repositories.property_installation_verification_repository import (
    PropertyInstallationVerificationRepository,
)


def create_installation(db_session):
    landlord_user = User(
        id=uuid.uuid4(),
        email=f"landlord-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Installation Test Landlord",
        phone="+254700000020",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-INSTALL-{uuid.uuid4().hex[:8].upper()}",
        name="Installation Test Property",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="active",
        property_id=property_record.id,
    )

    installer = User(
        id=uuid.uuid4(),
        email=f"installer-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.add(installer)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
    )

    db_session.add(installation)
    db_session.flush()

    return installation


def create_reviewer(db_session):
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(reviewer)
    db_session.flush()

    return reviewer



def test_add_and_get_by_id(db_session):
    installation = create_installation(db_session)
    reviewer = create_reviewer(db_session)

    verification = PropertyInstallationVerification(
        id=uuid.uuid4(),
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="verified",
        verified_at=datetime.now(UTC),
        notes="Verified successfully",
    )

    repository = PropertyInstallationVerificationRepository(db_session)
    result = repository.add(verification)

    assert result.id == verification.id
    assert result.installation_id == installation.id
    assert result.verified_by == reviewer.id

    fetched = repository.get_by_id(verification.id)

    assert fetched is not None
    assert fetched.id == verification.id
    assert fetched.status == "verified"
    assert fetched.notes == "Verified successfully"


def test_get_by_installation_id_returns_history_newest_first(db_session):
    installation = create_installation(db_session)
    reviewer = create_reviewer(db_session)

    older = PropertyInstallationVerification(
        id=uuid.uuid4(),
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="rejected",
        verified_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
        notes="Older decision",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    newer = PropertyInstallationVerification(
        id=uuid.uuid4(),
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="verified",
        verified_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
        notes="Newer decision",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    db_session.add(older)
    db_session.add(newer)
    db_session.flush()

    repository = PropertyInstallationVerificationRepository(db_session)
    results = repository.get_by_installation_id(installation.id)

    assert [item.id for item in results] == [newer.id, older.id]
    assert [item.status for item in results] == ["verified", "rejected"]


def test_get_latest_by_installation_id_returns_newest_record(db_session):
    installation = create_installation(db_session)
    reviewer = create_reviewer(db_session)

    older = PropertyInstallationVerification(
        id=uuid.uuid4(),
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="rejected",
        verified_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    newer = PropertyInstallationVerification(
        id=uuid.uuid4(),
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="verified",
        verified_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    db_session.add(older)
    db_session.add(newer)
    db_session.flush()

    repository = PropertyInstallationVerificationRepository(db_session)
    result = repository.get_latest_by_installation_id(installation.id)

    assert result is not None
    assert result.id == newer.id
    assert result.status == "verified"
