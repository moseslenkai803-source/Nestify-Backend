import uuid
from datetime import UTC, datetime
from threading import Event, Thread

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from tests.conftest import cleanup_installation_test_context

from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.installation_assignment import InstallationAssignment
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.property_verification import PropertyVerification
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

    property_address = PropertyAddress(
        id=uuid.uuid4(),
        property_id=property_record.id,
        formatted_address="Installation Service Address",
        county="Nairobi",
        sub_county="Westlands",
        locality="Installation Test Locality",
    )

    property_verification = PropertyVerification(
        id=uuid.uuid4(),
        property_id=property_record.id,
        verified_by=landlord_user.id,
        status="verified",
        verified_at=datetime.now(UTC),
        notes="Installation service test fixture",
    )

    db_session.add(property_address)
    db_session.add(property_verification)
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





def test_verify_assignment_linked_installation_completes_assignment(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Verification Assignment Contractor",
        contractor_type="company",
        status="active",
    )
    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-verification-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )
    contractor_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=contractor.id,
        user_id=contractor_user.id,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-assignment-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(contractor)
    db_session.add(contractor_user)
    db_session.add(reviewer)
    db_session.flush()

    db_session.add(contractor_member)
    db_session.flush()

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        contractor_id=contractor.id,
        contractor_member_id=contractor_member.id,
        assigned_by=installer.id,
        status="submitted",
    )
    db_session.add(assignment)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        assignment_id=assignment.id,
        installer_id=contractor_user.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
        notes="Contractor installation evidence.",
    )
    db_session.add(installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    result = service.verify_installation(
        property_id=property_record.id,
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="verified",
        notes="Installation evidence confirmed.",
    )

    assert result.status == "verified"
    assert installation.status == "verified"

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)
    assert fetched_assignment is not None
    assert fetched_assignment.status == "completed"

    lifecycle_service = AddressPlateLifecycleService(db_session)
    history = lifecycle_service.get_history(plate.id)

    assert [event.event_type for event in history] == [
        "manufactured",
        "allocated",
        "dispatched",
        "installed",
        "verified",
    ]

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


def test_verify_installation_serializes_concurrent_verification_attempts(
    db_session,
):
    landlord_user, installer, property_record, plate = create_installation_context(
        db_session
    )

    reviewer_one = User(
        id=uuid.uuid4(),
        email=f"reviewer-one-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    reviewer_two = User(
        id=uuid.uuid4(),
        email=f"reviewer-two-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

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

    db_session.add(reviewer_one)
    db_session.add(reviewer_two)
    db_session.add(installation)
    db_session.flush()

    installation_id = installation.id
    property_id = property_record.id

    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_locked = Event()
    second_started = Event()
    second_finished = Event()
    second_error = {}
    thread = None

    try:
        first_service = PropertyInstallationVerificationService(
            first_session
        )

        locked_installation = (
            first_service.property_installation_repository.get_by_id_for_update(
                installation_id
            )
        )

        assert locked_installation is not None
        assert locked_installation.status == "submitted"

        first_locked.set()

        def verify_from_second_transaction():
            try:
                second_service = PropertyInstallationVerificationService(
                    second_session
                )

                second_started.set()

                second_service.verify_installation(
                    property_id=property_id,
                    installation_id=installation_id,
                    verified_by=reviewer_two.id,
                    status="verified",
                )
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=verify_from_second_transaction)
        thread.start()

        assert first_locked.is_set()
        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_service.verify_installation(
            property_id=property_id,
            installation_id=installation_id,
            verified_by=reviewer_one.id,
            status="verified",
        )

        first_session.commit()

        assert second_finished.wait(timeout=2)

        thread.join(timeout=2)

        assert isinstance(second_error.get("error"), ValueError)
        assert str(second_error["error"]) == (
            "Installation is not awaiting verification"
        )

    finally:
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()

        cleanup_session = SessionLocal()
        try:
            cleanup_installation_test_context(
                cleanup_session,
                property_id,
                [
                    landlord_user.id,
                    installer.id,
                    reviewer_one.id,
                    reviewer_two.id,
                ],
            )
        finally:
            cleanup_session.close()



def test_verify_assignment_linked_installation_rejection_returns_assignment_to_in_progress(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Rejection Assignment Contractor",
        contractor_type="company",
        status="active",
    )
    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-rejection-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )
    contractor_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=contractor.id,
        user_id=contractor_user.id,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-rejection-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(contractor)
    db_session.add(contractor_user)
    db_session.add(reviewer)
    db_session.flush()

    db_session.add(contractor_member)
    db_session.flush()

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        contractor_id=contractor.id,
        contractor_member_id=contractor_member.id,
        assigned_by=installer.id,
        status="submitted",
    )
    db_session.add(assignment)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        assignment_id=assignment.id,
        installer_id=contractor_user.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
        notes="Contractor installation evidence.",
    )
    db_session.add(installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    result = service.verify_installation(
        property_id=property_record.id,
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="rejected",
        notes="Installation evidence requires correction.",
    )

    assert result.status == "rejected"
    assert installation.status == "rejected"

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)
    assert fetched_assignment is not None
    assert fetched_assignment.status == "in_progress"

    lifecycle_service = AddressPlateLifecycleService(db_session)
    history = lifecycle_service.get_history(plate.id)

    assert [event.event_type for event in history] == [
        "manufactured",
        "allocated",
        "dispatched",
    ]



def test_verify_cancelled_assignment_linked_installation_is_rejected(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Cancelled Assignment Contractor",
        contractor_type="company",
        status="active",
    )
    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-cancelled-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )
    contractor_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=contractor.id,
        user_id=contractor_user.id,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-cancelled-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(contractor)
    db_session.add(contractor_user)
    db_session.add(reviewer)
    db_session.flush()

    db_session.add(contractor_member)
    db_session.flush()

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        contractor_id=contractor.id,
        contractor_member_id=contractor_member.id,
        assigned_by=installer.id,
        status="cancelled",
    )
    db_session.add(assignment)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        assignment_id=assignment.id,
        installer_id=contractor_user.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
        notes="Installation evidence from cancelled assignment.",
    )
    db_session.add(installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    with pytest.raises(ValueError, match="Installation assignment is cancelled"):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="verified",
        )

    assert installation.status == "submitted"

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)
    assert fetched_assignment is not None
    assert fetched_assignment.status == "cancelled"



def test_verify_installation_rejects_assignment_property_mismatch(db_session):
    _, installer, property_record, plate = create_installation_context(db_session)

    second_property = Property(
        id=uuid.uuid4(),
        landlord_id=property_record.landlord_id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Assignment Mismatch Property",
        property_type="residential",
        status="verified",
    )
    second_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
        property_id=second_property.id,
    )
    db_session.add(second_property)
    db_session.flush()
    db_session.add(second_plate)
    db_session.flush()

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Property Mismatch Contractor",
        contractor_type="company",
        status="active",
    )
    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-property-mismatch-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )
    contractor_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=contractor.id,
        user_id=contractor_user.id,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-property-mismatch-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(contractor)
    db_session.add(contractor_user)
    db_session.add(reviewer)
    db_session.flush()

    db_session.add(contractor_member)
    db_session.flush()

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=second_property.id,
        plate_id=second_plate.id,
        contractor_id=contractor.id,
        contractor_member_id=contractor_member.id,
        assigned_by=installer.id,
        status="submitted",
    )
    db_session.add(assignment)
    db_session.flush()

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        assignment_id=assignment.id,
        installer_id=contractor_user.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
        notes="Installation evidence with mismatched assignment property.",
    )
    db_session.add(installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    try:
        with pytest.raises(
            ValueError,
            match="Installation assignment does not belong to this property",
        ):
            service.verify_installation(
                property_id=property_record.id,
                installation_id=installation.id,
                verified_by=reviewer.id,
                status="verified",
            )

        assert installation.status == "submitted"

        fetched_assignment = db_session.get(
            InstallationAssignment,
            assignment.id,
        )
        assert fetched_assignment is not None
        assert fetched_assignment.status == "submitted"
    finally:
        db_session.execute(
            text(
                "DELETE FROM property_installations "
                "WHERE id = :installation_id"
            ),
            {"installation_id": installation.id},
        )
        db_session.execute(
            text(
                "DELETE FROM installation_assignments "
                "WHERE id = :assignment_id"
            ),
            {"assignment_id": assignment.id},
        )
        db_session.execute(
            text(
                "DELETE FROM address_plates "
                "WHERE id = :plate_id"
            ),
            {"plate_id": second_plate.id},
        )
        db_session.execute(
            text(
                "DELETE FROM properties "
                "WHERE id = :property_id"
            ),
            {"property_id": second_property.id},
        )
        db_session.flush()


def test_list_pending_installations_returns_submitted_installations_for_authorized_properties(
    db_session,
):
    _, installer, property_record, plate = create_installation_context(db_session)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-queue-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(reviewer)
    db_session.flush()

    from app.services.property_access_service import PropertyAccessService

    PropertyAccessService(db_session).grant_access(
        user_id=reviewer.id,
        property_id=property_record.id,
        access_type="installation_verification",
    )

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

    result = service.list_pending_installations(reviewer)

    assert [item.id for item in result] == [installation.id]


def test_list_pending_installations_returns_all_submitted_installations_for_admin(
    db_session,
):
    _, installer, first_property, first_plate = create_installation_context(
        db_session
    )

    second_property = Property(
        id=uuid.uuid4(),
        landlord_id=first_property.landlord_id,
        property_code=f"NEST-QUEUE-ADMIN-SECOND-{uuid.uuid4().hex[:8].upper()}",
        name="Second Admin Queue Property",
        property_type="residential",
        status="verified",
    )

    second_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-QUEUE-ADMIN-SECOND-{uuid.uuid4().hex[:8].upper()}",
        status="unactivated",
        property_id=second_property.id,
    )

    admin = User(
        id=uuid.uuid4(),
        email=f"admin-queue-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="admin",
        is_active=True,
    )

    db_session.add(second_property)
    db_session.flush()

    db_session.add(second_plate)
    db_session.add(admin)
    db_session.flush()

    first_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=first_property.id,
        plate_id=first_plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
    )

    second_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=second_property.id,
        plate_id=second_plate.id,
        installer_id=installer.id,
        latitude=-1.287000,
        longitude=36.818000,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
    )

    verified_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=first_property.id,
        plate_id=first_plate.id,
        installer_id=installer.id,
        latitude=-1.288000,
        longitude=36.819000,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="verified",
    )

    db_session.add(first_installation)
    db_session.add(second_installation)
    db_session.add(verified_installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    result = service.list_pending_installations(admin)

    result_ids = {item.id for item in result}

    assert first_installation.id in result_ids
    assert second_installation.id in result_ids
    assert verified_installation.id not in result_ids



def test_list_pending_installations_excludes_properties_without_verification_access(
    db_session,
):
    _, installer, authorized_property, authorized_plate = create_installation_context(
        db_session
    )

    second_property = Property(
        id=uuid.uuid4(),
        landlord_id=authorized_property.landlord_id,
        property_code=f"NEST-QUEUE-SECOND-{uuid.uuid4().hex[:8].upper()}",
        name="Second Queue Property",
        property_type="residential",
        status="verified",
    )

    second_plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-QUEUE-SECOND-{uuid.uuid4().hex[:8].upper()}",
        status="unactivated",
        property_id=second_property.id,
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
    db_session.flush()

    db_session.add(second_plate)
    db_session.add(reviewer)
    db_session.flush()

    from app.services.property_access_service import PropertyAccessService

    PropertyAccessService(db_session).grant_access(
        user_id=reviewer.id,
        property_id=authorized_property.id,
        access_type="installation_verification",
    )

    authorized_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=authorized_property.id,
        plate_id=authorized_plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
    )

    unauthorized_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=second_property.id,
        plate_id=second_plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
    )

    db_session.add(authorized_installation)
    db_session.add(unauthorized_installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    result = service.list_pending_installations(reviewer)

    result_ids = [item.id for item in result]

    assert authorized_installation.id in result_ids
    assert unauthorized_installation.id not in result_ids


def test_list_pending_installations_excludes_non_submitted_installations(
    db_session,
):
    _, installer, property_record, plate = create_installation_context(db_session)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-status-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )

    db_session.add(reviewer)
    db_session.flush()

    from app.services.property_access_service import PropertyAccessService

    PropertyAccessService(db_session).grant_access(
        user_id=reviewer.id,
        property_id=property_record.id,
        access_type="installation_verification",
    )

    submitted_installation = PropertyInstallation(
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

    verified_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="verified",
    )

    db_session.add(submitted_installation)
    db_session.add(verified_installation)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    result = service.list_pending_installations(reviewer)

    result_ids = [item.id for item in result]

    assert submitted_installation.id in result_ids
    assert verified_installation.id not in result_ids
