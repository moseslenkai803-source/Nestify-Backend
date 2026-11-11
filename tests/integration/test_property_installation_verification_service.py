import uuid
from datetime import UTC, datetime
from threading import Event, Thread
from time import monotonic, sleep

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from tests.conftest import cleanup_installation_test_context

from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.property_access import PropertyAccess
from app.models.installation_assignment import InstallationAssignment
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.property_verification import PropertyVerification
from app.models.property_installation import PropertyInstallation
from app.models.property_installation_verification import (
    PropertyInstallationVerification,
)
from app.models.user import User
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.services.employee_service import EmployeeService
from app.services.property_access_service import PropertyAccessService
from app.services.property_installation_verification_service import (
    PropertyInstallationVerificationService,
)


def create_employee_record(db_session, user):
    db_session.add(
        Employee(
            user_id=user.id,
            employee_number=f"TEST-{uuid.uuid4().hex}",
            department="Operations",
            position="Test Employee",
        )
    )
    db_session.flush()



def authorize_installation_reviewer(db_session, user, property_id):
    employee = (
        db_session.query(Employee)
        .filter(Employee.user_id == user.id)
        .one_or_none()
    )

    if employee is None:
        employee = Employee(
            user_id=user.id,
            employee_number=f"TEST-{uuid.uuid4().hex}",
            department="Operations",
            position="Installation Verification",
        )
        db_session.add(employee)
        db_session.flush()

    clearance = (
        db_session.query(EmployeeClearance)
        .filter(
            EmployeeClearance.employee_id == employee.id,
            EmployeeClearance.clearance == "installation_verification",
        )
        .one_or_none()
    )

    if clearance is None:
        db_session.add(
            EmployeeClearance(
                employee_id=employee.id,
                clearance="installation_verification",
                is_active=True,
            )
        )
    else:
        clearance.is_active = True

    access = (
        db_session.query(PropertyAccess)
        .filter(
            PropertyAccess.user_id == user.id,
            PropertyAccess.property_id == property_id,
            PropertyAccess.access_type == "installation_verification",
        )
        .one_or_none()
    )

    if access is None:
        db_session.add(
            PropertyAccess(
                user_id=user.id,
                property_id=property_id,
                access_type="installation_verification",
                is_active=True,
            )
        )
    else:
        access.is_active = True

    db_session.flush()


def create_authorized_reviewer_context(db_session):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-revocation-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        is_active=True,
    )
    db_session.add(reviewer)
    db_session.flush()

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
    )

    employee = (
        db_session.query(Employee)
        .filter(Employee.user_id == reviewer.id)
        .one()
    )
    clearance = (
        db_session.query(EmployeeClearance)
        .filter(
            EmployeeClearance.employee_id == employee.id,
            EmployeeClearance.clearance == "installation_verification",
        )
        .one()
    )
    property_access = (
        db_session.query(PropertyAccess)
        .filter(
            PropertyAccess.user_id == reviewer.id,
            PropertyAccess.property_id == property_record.id,
            PropertyAccess.access_type == "installation_verification",
        )
        .one()
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

    return (
        reviewer,
        employee,
        clearance,
        property_access,
        property_record,
        installation,
        service,
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

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
    )

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

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
    )

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

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
    )

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

def test_ended_employee_cannot_verify_or_view_pending_installations(
    db_session,
):
    (
        reviewer,
        employee,
        _,
        _,
        property_record,
        installation,
        service,
    ) = create_authorized_reviewer_context(db_session)

    employee.ended_at = datetime.now(UTC)
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="User is not authorized to verify installations",
    ):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="verified",
        )

    with pytest.raises(
        ValueError,
        match="User is not authorized to verify installations",
    ):
        service.list_pending_installations(reviewer)

    db_session.refresh(installation)
    assert installation.status == "submitted"

    verification_count = (
        db_session.query(PropertyInstallationVerification)
        .filter(
            PropertyInstallationVerification.installation_id
            == installation.id
        )
        .count()
    )
    assert verification_count == 0


def test_employee_with_inactive_clearance_cannot_verify_or_view_pending(
    db_session,
):
    (
        reviewer,
        _,
        clearance,
        _,
        property_record,
        installation,
        service,
    ) = create_authorized_reviewer_context(db_session)

    clearance.is_active = False
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="User is not authorized to verify installations",
    ):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="verified",
        )

    with pytest.raises(
        ValueError,
        match="User is not authorized to verify installations",
    ):
        service.list_pending_installations(reviewer)

    db_session.refresh(installation)
    assert installation.status == "submitted"

    verification_count = (
        db_session.query(PropertyInstallationVerification)
        .filter(
            PropertyInstallationVerification.installation_id
            == installation.id
        )
        .count()
    )
    assert verification_count == 0


def test_employee_with_inactive_property_access_cannot_verify_or_view_property(
    db_session,
):
    (
        reviewer,
        _,
        _,
        property_access,
        property_record,
        installation,
        service,
    ) = create_authorized_reviewer_context(db_session)

    property_access.is_active = False
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="User is not authorized to verify installations",
    ):
        service.verify_installation(
            property_id=property_record.id,
            installation_id=installation.id,
            verified_by=reviewer.id,
            status="verified",
        )

    assert service.list_pending_installations(reviewer) == []

    db_session.refresh(installation)
    assert installation.status == "submitted"

    verification_count = (
        db_session.query(PropertyInstallationVerification)
        .filter(
            PropertyInstallationVerification.installation_id
            == installation.id
        )
        .count()
    )
    assert verification_count == 0


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


@pytest.mark.independent_db_transactions
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

    authorize_installation_reviewer(
        db_session,
        reviewer_one,
        property_record.id,
    )
    authorize_installation_reviewer(
        db_session,
        reviewer_two,
        property_record.id,
    )

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
        first_session.rollback()

        if thread is not None:
            thread.join(timeout=5)

        thread_stopped = thread is None or not thread.is_alive()

        first_session.close()

        if thread_stopped:
            second_session.rollback()
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

        assert thread_stopped, (
            "Concurrent verification thread did not terminate"
        )





def _assert_revocation_race_rejects_verification(
    db_session,
    revoke_authorization,
):
    (
        reviewer,
        employee,
        clearance,
        property_access,
        property_record,
        installation,
        _,
    ) = create_authorized_reviewer_context(db_session)

    reviewer_id = reviewer.id
    employee_id = employee.id
    property_id = property_record.id
    installation_id = installation.id
    installer_user_id = installation.installer_id
    landlord_user_id = (
        db_session.query(Landlord.user_id)
        .filter(Landlord.id == property_record.landlord_id)
        .scalar()
    )
    assert landlord_user_id is not None

    db_session.commit()

    revocation_session = SessionLocal()
    verification_session = SessionLocal()

    verification_backend_pid = verification_session.execute(
        text("SELECT pg_backend_pid()")
    ).scalar_one()

    verification_started = Event()
    verification_finished = Event()
    verification_error = {}
    thread = None

    try:
        revoke_authorization(
            revocation_session,
            employee_id,
            reviewer_id,
            property_id,
        )

        def verify_in_separate_transaction():
            try:
                service = PropertyInstallationVerificationService(
                    verification_session
                )
                verification_started.set()

                service.verify_installation(
                    property_id=property_id,
                    installation_id=installation_id,
                    verified_by=reviewer_id,
                    status="verified",
                )
            except Exception as exc:
                verification_error["error"] = exc
            finally:
                verification_finished.set()

        thread = Thread(target=verify_in_separate_transaction)
        thread.start()

        assert verification_started.wait(timeout=2)

        # Confirm PostgreSQL reports that verification is actually waiting
        # for a row lock held by the revocation transaction.
        lock_wait_deadline = monotonic() + 3
        lock_wait_observed = False

        while monotonic() < lock_wait_deadline:
            wait_event_type = db_session.execute(
                text(
                    "SELECT wait_event_type "
                    "FROM pg_stat_activity "
                    "WHERE pid = :pid"
                ),
                {"pid": verification_backend_pid},
            ).scalar_one_or_none()

            if wait_event_type == "Lock":
                lock_wait_observed = True
                break

            if verification_finished.is_set():
                break

            sleep(0.01)

        assert lock_wait_observed, (
            "Verification never entered a PostgreSQL lock wait"
        )

        # The revocation owns the authorization-row lock. Committing it
        # allows the waiting verification transaction to read the new state.
        revocation_session.commit()

        assert verification_finished.wait(timeout=3)
        thread.join(timeout=3)
        assert not thread.is_alive()

        error = verification_error.get("error")
        assert isinstance(error, ValueError)
        assert str(error) == (
            "User is not authorized to verify installations"
        )

        observer_session = SessionLocal()
        try:
            persisted_installation = (
                observer_session.query(PropertyInstallation)
                .filter(PropertyInstallation.id == installation_id)
                .one()
            )
            verification_count = (
                observer_session.query(PropertyInstallationVerification)
                .filter(
                    PropertyInstallationVerification.installation_id
                    == installation_id
                )
                .count()
            )

            assert persisted_installation.status == "submitted"
            assert verification_count == 0
        finally:
            observer_session.close()

    finally:
        # Release any held authorization-row lock before waiting for the worker.
        revocation_session.rollback()

        if thread is not None:
            thread.join(timeout=5)

        thread_stopped = thread is None or not thread.is_alive()

        revocation_session.close()

        if thread_stopped:
            verification_session.rollback()
            verification_session.close()

            cleanup_session = SessionLocal()
            try:
                cleanup_installation_test_context(
                    cleanup_session,
                    property_id,
                    [reviewer_id, installer_user_id, landlord_user_id],
                )
            finally:
                cleanup_session.close()

        assert thread_stopped, (
            "Concurrent verification thread did not terminate"
        )


@pytest.mark.independent_db_transactions
def test_clearance_revocation_racing_verification_rejects_verification(
    db_session,
):
    def revoke_clearance(
        session,
        employee_id,
        reviewer_id,
        property_id,
    ):
        EmployeeService(session).remove_clearance(
            employee_id=employee_id,
            clearance="installation_verification",
        )

    _assert_revocation_race_rejects_verification(
        db_session,
        revoke_clearance,
    )


@pytest.mark.independent_db_transactions
def test_property_access_revocation_racing_verification_rejects_verification(
    db_session,
):
    def revoke_property_access(
        session,
        employee_id,
        reviewer_id,
        property_id,
    ):
        PropertyAccessService(session).revoke_access(
            user_id=reviewer_id,
            property_id=property_id,
            access_type="installation_verification",
        )

    _assert_revocation_race_rejects_verification(
        db_session,
        revoke_property_access,
    )


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

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
    )

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



@pytest.mark.parametrize("resolution_status", ["verified", "rejected"])
def test_verify_cancelled_assignment_linked_installation_can_be_resolved(db_session, resolution_status):
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

    cancelled_at = datetime.now(UTC)
    cancellation_reason = "Cancelled while evidence awaited review"

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        contractor_id=contractor.id,
        contractor_member_id=contractor_member.id,
        assigned_by=installer.id,
        status="cancelled",
        cancelled_by=installer.id,
        cancelled_at=cancelled_at,
        cancellation_reason=cancellation_reason,
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

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
    )

    service = PropertyInstallationVerificationService(db_session)

    verification = service.verify_installation(
        property_id=property_record.id,
        installation_id=installation.id,
        verified_by=reviewer.id,
        status=resolution_status,
    )

    assert verification.status == resolution_status
    assert installation.status == resolution_status

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)
    assert fetched_assignment is not None
    assert fetched_assignment.status == "cancelled"
    assert fetched_assignment.cancelled_by == installer.id
    assert fetched_assignment.cancelled_at == cancelled_at
    assert fetched_assignment.cancellation_reason == cancellation_reason



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

    create_employee_record(db_session, reviewer)
    from app.services.property_access_service import PropertyAccessService

    PropertyAccessService(db_session).grant_access(
        user_id=reviewer.id,
        property_id=property_record.id,
        access_type="installation_verification",
    )

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
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

    create_employee_record(db_session, reviewer)
    from app.services.property_access_service import PropertyAccessService

    PropertyAccessService(db_session).grant_access(
        user_id=reviewer.id,
        property_id=authorized_property.id,
        access_type="installation_verification",
    )

    authorize_installation_reviewer(
        db_session,
        reviewer,
        authorized_property.id,
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

    create_employee_record(db_session, reviewer)
    from app.services.property_access_service import PropertyAccessService

    PropertyAccessService(db_session).grant_access(
        user_id=reviewer.id,
        property_id=property_record.id,
        access_type="installation_verification",
    )

    authorize_installation_reviewer(
        db_session,
        reviewer,
        property_record.id,
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


@pytest.mark.parametrize("reviewer_role", ["admin", "reviewer"])
def test_pending_queue_includes_installation_from_cancelled_assignment(
    db_session,
    reviewer_role,
):
    _, installer, property_record, plate = create_installation_context(db_session)

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Cancelled Queue Contractor",
        contractor_type="company",
        status="active",
    )
    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-queue-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-queue-cancelled-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="admin" if reviewer_role == "admin" else "employee",
        clearance=(
            None
            if reviewer_role == "admin"
            else "installation_verification"
        ),
        is_active=True,
    )

    db_session.add_all([contractor, contractor_user, reviewer])
    db_session.flush()

    contractor_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=contractor.id,
        user_id=contractor_user.id,
        is_active=True,
    )
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

    cancelled_assignment_installation = PropertyInstallation(
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
        notes="Evidence retained after assignment cancellation.",
    )
    _, legacy_installer, legacy_property, legacy_plate = (
        create_installation_context(db_session)
    )

    legacy_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=legacy_property.id,
        plate_id=legacy_plate.id,
        installer_id=legacy_installer.id,
        latitude=-1.287000,
        longitude=36.818000,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="submitted",
        notes="Legacy installation without an assignment.",
    )
    db_session.add_all(
        [cancelled_assignment_installation, legacy_installation]
    )
    db_session.flush()

    if reviewer_role == "reviewer":
        create_employee_record(db_session, reviewer)
        from app.services.property_access_service import PropertyAccessService

        property_access_service = PropertyAccessService(db_session)

        property_access_service.grant_access(
            user_id=reviewer.id,
            property_id=property_record.id,
            access_type="installation_verification",
        )
        property_access_service.grant_access(
            user_id=reviewer.id,
            property_id=legacy_property.id,
            access_type="installation_verification",
        )

        authorize_installation_reviewer(
            db_session,
            reviewer,
            property_record.id,
        )

    service = PropertyInstallationVerificationService(db_session)
    result = service.list_pending_installations(reviewer)
    result_ids = {item.id for item in result}

    assert cancelled_assignment_installation.id in result_ids
    assert legacy_installation.id in result_ids

    # Verify persisted records remain unchanged after queue filtering.
    db_session.refresh(cancelled_assignment_installation)
    db_session.refresh(assignment)

    assert cancelled_assignment_installation.status == "submitted"
    assert assignment.status == "cancelled"


def test_admin_reviewer_rejected_when_locked_user_role_has_changed(
    db_session,
    monkeypatch,
):
    admin = User(
        id=uuid.uuid4(),
        email=f"admin-role-change-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="admin",
        is_active=True,
    )

    db_session.add(admin)
    db_session.flush()

    service = PropertyInstallationVerificationService(db_session)

    # Simulate the current database record having a different role
    # when the locked user record is retrieved.
    locked_user = User(
        id=admin.id,
        email=admin.email,
        password_hash="hashed-password",
        role="employee",
        is_active=True,
    )

    monkeypatch.setattr(
        service.user_repository,
        "get_by_id_for_update",
        lambda user_id: locked_user,
    )

    with pytest.raises(
        ValueError,
        match="User is not authorized to verify installations",
    ):
        service._authorize_reviewer(admin)
