import uuid
from datetime import UTC, datetime

import pytest

from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_installation import PropertyInstallation
from app.models.user import User
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.services.property_installation_verification_service import (
    PropertyInstallationVerificationService,
)


def create_installation_context(db_session):
    landlord_user = User(
        id=uuid.uuid4(),
        email=f"landlord-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    installer = User(
        id=uuid.uuid4(),
        email=f"installer-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Installation Service Landlord",
        phone="+254700000030",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Installation Service Property",
        property_type="residential",
        status="verified",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
        property_id=property_record.id,
    )

    db_session.add(landlord_user)
    db_session.add(installer)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    lifecycle_service = AddressPlateLifecycleService(db_session)

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=installer.id,
    )

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="allocated",
        performed_by=installer.id,
    )

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="dispatched",
        performed_by=installer.id,
    )

    return landlord_user, installer, property_record, plate



def test_verify_installation_marks_installation_verified(db_session):
    _, _, property_record, plate = create_installation_context(db_session)

    installer = User(
        id=uuid.uuid4(),
        email=f"installer-test-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(installer)
    db_session.add(reviewer)
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

    service = PropertyInstallationVerificationService(db_session)

    result = service.verify_installation(
        property_id=property_record.id,
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="verified",
        notes="GPS location and installation evidence confirmed",
    )

    assert result.installation_id == installation.id
    assert result.verified_by == reviewer.id
    assert result.status == "verified"
    assert result.notes == "GPS location and installation evidence confirmed"
    assert result.verified_at is not None
    assert result.created_at is not None
    assert installation.status == "verified"

    lifecycle_service = AddressPlateLifecycleService(db_session)

    history = lifecycle_service.get_history(plate.id)

    assert [event.event_type for event in history] == [
        "manufactured",
        "allocated",
        "dispatched",
        "installed",
        "verified",
    ]
    assert history[-2].performed_by == installer.id
    assert history[-2].notes is None
    assert history[-1].performed_by == reviewer.id
    assert history[-1].notes == "GPS location and installation evidence confirmed"

def test_verify_installation_marks_installation_rejected(db_session):
    _, _, property_record, plate = create_installation_context(db_session)

    installer = User(
        id=uuid.uuid4(),
        email=f"installer-reject-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-reject-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(installer)
    db_session.add(reviewer)
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

    service = PropertyInstallationVerificationService(db_session)

    result = service.verify_installation(
        property_id=property_record.id,
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="rejected",
        notes="Installation evidence requires correction",
    )

    assert result.installation_id == installation.id
    assert result.verified_by == reviewer.id
    assert result.status == "rejected"
    assert result.notes == "Installation evidence requires correction"
    assert result.verified_at is not None
    assert installation.status == "rejected"

    lifecycle_service = AddressPlateLifecycleService(db_session)

    history = lifecycle_service.get_history(plate.id)

    assert [event.event_type for event in history] == [
        "manufactured",
        "allocated",
        "dispatched",
    ]

def test_verify_installation_rejects_invalid_status(db_session):
    _, _, property_record, plate = create_installation_context(db_session)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-invalid-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(reviewer)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=reviewer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
    )

    db_session.add(installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Verification status must be 'verified' or 'rejected'",
    ):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="pending",
        )

def test_verify_installation_rejects_non_submitted_installation(db_session):
    _, _, property_record, plate = create_installation_context(db_session)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-state-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(reviewer)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=reviewer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="verified",
    )

    db_session.add(installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Installation is not awaiting verification",
    ):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="rejected",
        )

def test_verify_installation_requires_existing_verifier(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

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

    service = PropertyInstallationVerificationService(db_session)

    with pytest.raises(ValueError, match="Verifier not found"):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=uuid.uuid4(),
            status="verified",
        )

def test_verify_installation_rejects_inactive_verifier(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"inactive-reviewer-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=False,
    )

    db_session.add(reviewer)
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

    service = PropertyInstallationVerificationService(db_session)

    with pytest.raises(ValueError, match="Verifier is inactive"):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="verified",
        )

def test_verify_installation_rejects_wrong_property(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

    second_property = Property(
        id=uuid.uuid4(),
        landlord_id=property_record.landlord_id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Second Installation Property",
        property_type="residential",
        status="verified",
    )

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-scope-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(second_property)
    db_session.add(reviewer)
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

    service = PropertyInstallationVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Installation does not belong to this property",
    ):
        service.verify_installation(
            property_id=second_property.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="verified",
        )
