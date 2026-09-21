import uuid
from datetime import UTC, datetime, timedelta

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_verification import PropertyVerification
from app.models.user import User
from app.repositories.property_verification_repository import (
    PropertyVerificationRepository,
)


def test_add_persists_property_verification(db_session):
    user = User(
        id=uuid.uuid4(),
        email="verification-add-test@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email="verification-landlord-test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Verification Test Landlord",
        phone="+254700000010",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-VERIFY-001",
        name="Verification Property",
        property_type="residential",
        status="draft",
    )

    verification = PropertyVerification(
        property_id=property_record.id,
        verified_by=user.id,
        status="verified",
        verified_at=datetime.now(UTC),
        notes="Property verified successfully",
    )

    db_session.add(user)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    repository = PropertyVerificationRepository(db_session)

    result = repository.add(verification)

    assert result is verification
    assert result.id is not None
    assert result.property_id == property_record.id
    assert result.verified_by == user.id
    assert result.status == "verified"
    assert result.notes == "Property verified successfully"


def test_get_by_property_id_returns_verification_history(db_session):
    user = User(
        id=uuid.uuid4(),
        email="verification-history-test@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email="verification-history-landlord@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Verification History Landlord",
        phone="+254700000011",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-VERIFY-002",
        name="Verification History Property",
        property_type="commercial",
        status="draft",
    )

    first_verification = PropertyVerification(
        id=uuid.uuid4(),
        property_id=property_record.id,
        verified_by=user.id,
        status="rejected",
        verified_at=datetime.now(UTC) - timedelta(minutes=5),
        notes="Additional information required",
    )

    second_verification = PropertyVerification(
        id=uuid.uuid4(),
        property_id=property_record.id,
        verified_by=user.id,
        status="verified",
        verified_at=datetime.now(UTC),
        notes="Property verified after resubmission",
    )

    db_session.add(user)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add_all([
        first_verification,
        second_verification,
    ])
    db_session.flush()

    repository = PropertyVerificationRepository(db_session)

    result = repository.get_by_property_id(property_record.id)

    assert len(result) == 2
    assert result[0].id == second_verification.id
    assert result[0].status == "verified"
    assert result[1].id == first_verification.id
    assert result[1].status == "rejected"


def test_get_latest_by_property_id_returns_newest_verification(db_session):
    user = User(
        id=uuid.uuid4(),
        email="verification-latest-test@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email="verification-latest-landlord@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Latest Verification Landlord",
        phone="+254700000012",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-VERIFY-003",
        name="Latest Verification Property",
        property_type="residential",
        status="draft",
    )

    older_verification = PropertyVerification(
        id=uuid.uuid4(),
        property_id=property_record.id,
        verified_by=user.id,
        status="rejected",
        verified_at=datetime.now(UTC) - timedelta(minutes=10),
        notes="First review",
    )

    latest_verification = PropertyVerification(
        id=uuid.uuid4(),
        property_id=property_record.id,
        verified_by=user.id,
        status="verified",
        verified_at=datetime.now(UTC),
        notes="Latest review",
    )

    db_session.add(user)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add_all([
        older_verification,
        latest_verification,
    ])
    db_session.flush()

    repository = PropertyVerificationRepository(db_session)

    result = repository.get_latest_by_property_id(property_record.id)

    assert result is not None
    assert result.id == latest_verification.id
    assert result.status == "verified"
    assert result.notes == "Latest review"
