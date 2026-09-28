import uuid
from datetime import UTC, datetime, timedelta

from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.installation_assignment import InstallationAssignment
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.repositories.installation_assignment_repository import (
    InstallationAssignmentRepository,
)


def create_assignment_context(db_session):
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
        display_name="Assignment Test Landlord",
        phone="+254700000030",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-ASSIGN-{uuid.uuid4().hex[:8].upper()}",
        name="Assignment Test Property",
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
        name="Assignment Test Contractor",
        contractor_type="company",
        status="active",
    )

    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-member-{uuid.uuid4()}@example.com",
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


def create_assignment(
    db_session,
    context,
    *,
    status="assigned",
    created_at=None,
    due_at=None,
):
    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        assigned_at=created_at or datetime.now(UTC),
        due_at=due_at,
        status=status,
        created_at=created_at or datetime.now(UTC),
    )

    db_session.add(assignment)
    db_session.flush()

    return assignment


def test_add_and_get_by_id(db_session):
    context = create_assignment_context(db_session)

    assignment = create_assignment(
        db_session,
        context,
        due_at=datetime(2026, 10, 1, 10, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    result = repository.add(assignment)

    assert result.id == assignment.id

    fetched = repository.get_by_id(assignment.id)

    assert fetched is not None
    assert fetched.id == assignment.id
    assert fetched.property_id == context["property"].id
    assert fetched.plate_id == context["plate"].id
    assert fetched.contractor_id == context["contractor"].id
    assert fetched.contractor_member_id == context["contractor_member"].id
    assert fetched.assigned_by == context["assigning_employee"].id
    assert fetched.status == "assigned"


def test_get_by_id_for_update_returns_assignment(db_session):
    context = create_assignment_context(db_session)

    assignment = create_assignment(db_session, context)

    repository = InstallationAssignmentRepository(db_session)

    result = repository.get_by_id_for_update(assignment.id)

    assert result is not None
    assert result.id == assignment.id


def test_get_active_by_property_id_returns_active_assignment(db_session):
    context = create_assignment_context(db_session)

    assignment = create_assignment(
        db_session,
        context,
        status="in_progress",
    )

    repository = InstallationAssignmentRepository(db_session)

    result = repository.get_active_by_property_id(context["property"].id)

    assert result is not None
    assert result.id == assignment.id
    assert result.status == "in_progress"


def test_get_active_by_property_id_ignores_completed_and_cancelled(
    db_session,
):
    context = create_assignment_context(db_session)

    create_assignment(
        db_session,
        context,
        status="completed",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    create_assignment(
        db_session,
        context,
        status="cancelled",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    result = repository.get_active_by_property_id(context["property"].id)

    assert result is None


def test_get_active_by_property_id_returns_newest_active_assignment(
    db_session,
):
    context = create_assignment_context(db_session)

    older = create_assignment(
        db_session,
        context,
        status="completed",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    newer = create_assignment(
        db_session,
        context,
        status="in_progress",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    result = repository.get_active_by_property_id(context["property"].id)

    assert result is not None
    assert result.id == newer.id
    assert result.id != older.id


def test_get_active_by_plate_id_returns_active_assignment(db_session):
    context = create_assignment_context(db_session)

    assignment = create_assignment(
        db_session,
        context,
        status="submitted",
    )

    repository = InstallationAssignmentRepository(db_session)

    result = repository.get_active_by_plate_id(context["plate"].id)

    assert result is not None
    assert result.id == assignment.id
    assert result.status == "submitted"


def test_get_active_by_plate_id_ignores_completed_and_cancelled(
    db_session,
):
    context = create_assignment_context(db_session)

    create_assignment(
        db_session,
        context,
        status="completed",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    create_assignment(
        db_session,
        context,
        status="cancelled",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    result = repository.get_active_by_plate_id(context["plate"].id)

    assert result is None


def test_get_by_contractor_id_returns_newest_first(db_session):
    context = create_assignment_context(db_session)

    older = create_assignment(
        db_session,
        context,
        status="completed",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    newer = create_assignment(
        db_session,
        context,
        status="in_progress",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    results = repository.get_by_contractor_id(context["contractor"].id)

    assert [item.id for item in results] == [newer.id, older.id]


def test_get_by_contractor_member_id_returns_assignments(db_session):
    context = create_assignment_context(db_session)

    assignment = create_assignment(db_session, context)

    repository = InstallationAssignmentRepository(db_session)

    results = repository.get_by_contractor_member_id(
        context["contractor_member"].id
    )

    assert [item.id for item in results] == [assignment.id]


def test_get_by_property_id_returns_newest_first(db_session):
    context = create_assignment_context(db_session)

    older = create_assignment(
        db_session,
        context,
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    newer = create_assignment(
        db_session,
        context,
        status="completed",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    results = repository.get_by_property_id(context["property"].id)

    assert [item.id for item in results] == [newer.id, older.id]


def test_active_queries_ignore_completed_and_cancelled_but_include_submitted(
    db_session,
):
    context = create_assignment_context(db_session)

    create_assignment(
        db_session,
        context,
        status="completed",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    submitted = create_assignment(
        db_session,
        context,
        status="submitted",
        created_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    repository = InstallationAssignmentRepository(db_session)

    property_result = repository.get_active_by_property_id(
        context["property"].id
    )
    plate_result = repository.get_active_by_plate_id(
        context["plate"].id
    )

    assert property_result is not None
    assert property_result.id == submitted.id

    assert plate_result is not None
    assert plate_result.id == submitted.id
