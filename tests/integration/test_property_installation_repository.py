import uuid
from datetime import UTC, datetime

from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.installation_assignment import InstallationAssignment
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_installation import PropertyInstallation
from app.models.user import User
from app.repositories.property_installation_repository import (
    PropertyInstallationRepository,
)


def create_installation_context(db_session):
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
        display_name="Installation Repository Landlord",
        phone="+254700000050",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-INSTALL-REPO-{uuid.uuid4().hex[:8].upper()}",
        name="Installation Repository Property",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="active",
        property_id=property_record.id,
    )

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Installation Repository Contractor",
        contractor_type="company",
        status="active",
    )

    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-{uuid.uuid4()}@example.com",
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

    assigning_employee = User(
        id=uuid.uuid4(),
        email=f"assigner-{uuid.uuid4()}@example.com",
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
    db_session.add(contractor)
    db_session.add(contractor_user)
    db_session.add(assigning_employee)
    db_session.flush()
    db_session.add(contractor_member)
    db_session.flush()

    return {
        "property": property_record,
        "plate": plate,
        "contractor": contractor,
        "contractor_member": contractor_member,
        "assigning_employee": assigning_employee,
    }


def create_assignment(db_session, context):
    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="in_progress",
    )

    db_session.add(assignment)
    db_session.flush()

    return assignment


def create_installation(
    db_session,
    context,
    assignment,
    *,
    created_at=None,
):
    timestamp = created_at or datetime.now(UTC)

    installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        assignment_id=assignment.id,
        installer_id=context["contractor_member"].user_id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=timestamp,
        status="submitted",
        notes="Installation repository test",
        created_at=timestamp,
    )

    db_session.add(installation)
    db_session.flush()

    return installation


def test_get_by_assignment_id_returns_linked_installation(db_session):
    context = create_installation_context(db_session)
    assignment = create_assignment(db_session, context)
    installation = create_installation(db_session, context, assignment)

    repository = PropertyInstallationRepository(db_session)

    result = repository.get_by_assignment_id(assignment.id)

    assert result is not None
    assert result.id == installation.id
    assert result.assignment_id == assignment.id


def test_get_by_assignment_id_returns_newest_installation(db_session):
    context = create_installation_context(db_session)
    assignment = create_assignment(db_session, context)

    older = create_installation(
        db_session,
        context,
        assignment,
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    newer = create_installation(
        db_session,
        context,
        assignment,
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = PropertyInstallationRepository(db_session)

    result = repository.get_by_assignment_id(assignment.id)

    assert result is not None
    assert result.id == newer.id
    assert result.id != older.id


def test_get_by_assignment_id_returns_none_when_no_installation_exists(db_session):
    context = create_installation_context(db_session)
    assignment = create_assignment(db_session, context)

    repository = PropertyInstallationRepository(db_session)

    result = repository.get_by_assignment_id(assignment.id)

    assert result is None


def test_get_by_assignment_id_for_update_returns_latest_installation(db_session):
    context = create_installation_context(db_session)
    assignment = create_assignment(db_session, context)
    installation = create_installation(db_session, context, assignment)

    repository = PropertyInstallationRepository(db_session)

    result = repository.get_by_assignment_id_for_update(assignment.id)

    assert result is not None
    assert result.id == installation.id
    assert result.assignment_id == assignment.id
