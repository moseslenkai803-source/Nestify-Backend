import uuid
from datetime import UTC, datetime
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal
from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.installation_assignment import InstallationAssignment
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.installation_assignment_service import (
    InstallationAssignmentService,
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
        display_name="Assignment Service Landlord",
        phone="+254700000040",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-ASSIGN-SVC-{uuid.uuid4().hex[:8].upper()}",
        name="Assignment Service Property",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
        property_id=property_record.id,
    )

    contractor = Contractor(
        id=uuid.uuid4(),
        name="Assignment Service Contractor",
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
        "landlord_user": landlord_user,
        "property": property_record,
        "plate": plate,
        "contractor": contractor,
        "contractor_user": contractor_user,
        "contractor_member": contractor_member,
        "assigning_employee": assigning_employee,
    }


def test_create_assignment_creates_assigned_record(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    due_at = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)

    result = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        due_at=due_at,
    )

    assert result.property_id == context["property"].id
    assert result.plate_id == context["plate"].id
    assert result.contractor_id == context["contractor"].id
    assert result.contractor_member_id == context["contractor_member"].id
    assert result.assigned_by == context["assigning_employee"].id
    assert result.due_at == due_at
    assert result.status == "assigned"
    assert result.assigned_at is not None
    assert result.created_at is not None
    assert result.updated_at is not None

    fetched = db_session.get(InstallationAssignment, result.id)

    assert fetched is not None
    assert fetched.id == result.id
    assert fetched.status == "assigned"


def test_create_assignment_requires_existing_property(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.create_assignment(
            property_id=uuid.uuid4(),
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_requires_existing_plate(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Address plate not found"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=uuid.uuid4(),
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_requires_plate_linked_to_property(db_session):
    context = create_assignment_context(db_session)

    other_landlord_user = User(
        id=uuid.uuid4(),
        email=f"other-landlord-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    other_landlord = Landlord(
        id=uuid.uuid4(),
        user_id=other_landlord_user.id,
        display_name="Other Assignment Landlord",
        phone="+254700000041",
        landlord_type="individual",
    )

    other_property = Property(
        id=uuid.uuid4(),
        landlord_id=other_landlord.id,
        property_code=f"NEST-OTHER-ASSIGN-{uuid.uuid4().hex[:8].upper()}",
        name="Other Assignment Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(other_landlord_user)
    db_session.flush()

    db_session.add(other_landlord)
    db_session.flush()

    db_session.add(other_property)
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate is not linked to this property",
    ):
        service.create_assignment(
            property_id=other_property.id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_requires_existing_contractor(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Contractor not found"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=uuid.uuid4(),
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_rejects_inactive_contractor(db_session):
    context = create_assignment_context(db_session)

    context["contractor"].status = "inactive"
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Contractor is inactive"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_requires_existing_contractor_member(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Contractor member not found"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=uuid.uuid4(),
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_rejects_member_from_another_contractor(db_session):
    context = create_assignment_context(db_session)

    other_contractor = Contractor(
        id=uuid.uuid4(),
        name="Other Assignment Contractor",
        contractor_type="company",
        status="active",
    )

    db_session.add(other_contractor)
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor member does not belong to this contractor",
    ):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=other_contractor.id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_rejects_inactive_contractor_member(db_session):
    context = create_assignment_context(db_session)

    context["contractor_member"].is_active = False
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Contractor member is inactive"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_rejects_inactive_contractor_member_user(db_session):
    context = create_assignment_context(db_session)

    context["contractor_user"].is_active = False
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor member user is inactive",
    ):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_requires_existing_assigning_user(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Assigning employee not found"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=uuid.uuid4(),
        )


def test_create_assignment_rejects_inactive_assigning_user(db_session):
    context = create_assignment_context(db_session)

    context["assigning_employee"].is_active = False
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(ValueError, match="Assigning employee is inactive"):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_requires_employee_assigner(db_session):
    context = create_assignment_context(db_session)

    context["assigning_employee"].role = "landlord"
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Only Nestify employees can assign installations",
    ):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_serializes_concurrent_assignments_for_same_property(
    db_session,
):
    context = create_assignment_context(db_session)

    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    second_started = Event()
    second_finished = Event()
    second_error = {}

    try:
        first_service = InstallationAssignmentService(first_session)

        locked_property = (
            first_service.property_repository.get_by_id_for_update(
                context["property"].id
            )
        )

        assert locked_property is not None

        def create_from_second_transaction():
            try:
                second_service = InstallationAssignmentService(second_session)

                second_started.set()

                second_service.create_assignment(
                    property_id=context["property"].id,
                    plate_id=context["plate"].id,
                    contractor_id=context["contractor"].id,
                    contractor_member_id=context["contractor_member"].id,
                    assigned_by=context["assigning_employee"].id,
                )
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=create_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.5)

        first_assignment = first_service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )

        first_session.commit()

        assert first_assignment.status == "assigned"

        assert second_finished.wait(timeout=5)
        thread.join(timeout=2)

        assert len(second_error) == 1
        assert isinstance(second_error["error"], ValueError)
        assert str(second_error["error"]) == (
            "Property already has an active installation assignment"
        )

        second_session.rollback()

        verification_session = SessionLocal()
        try:
            assignments = (
                verification_session.query(InstallationAssignment)
                .filter(
                    InstallationAssignment.property_id
                    == context["property"].id
                )
                .all()
            )

            assert len(assignments) == 1
            assert assignments[0].status == "assigned"
            assert assignments[0].id == first_assignment.id
        finally:
            verification_session.rollback()
            verification_session.close()

    finally:
        if not second_started.is_set():
            second_started.set()

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()


def test_create_assignment_rejects_existing_active_property_assignment(
    db_session,
):
    context = create_assignment_context(db_session)

    existing = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="assigned",
    )

    db_session.add(existing)
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Property already has an active installation assignment",
    ):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_create_assignment_rejects_existing_active_plate_assignment(
    db_session,
):
    context = create_assignment_context(db_session)

    other_landlord_user = User(
        id=uuid.uuid4(),
        email=f"other-landlord-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    other_landlord = Landlord(
        id=uuid.uuid4(),
        user_id=other_landlord_user.id,
        display_name="Other Assignment Landlord",
        phone="+254700000042",
        landlord_type="individual",
    )

    other_property = Property(
        id=uuid.uuid4(),
        landlord_id=other_landlord.id,
        property_code=f"NEST-OTHER-PLATE-{uuid.uuid4().hex[:8].upper()}",
        name="Other Assignment Plate Property",
        property_type="residential",
        status="draft",
    )

    other_contractor_user = User(
        id=uuid.uuid4(),
        email=f"other-contractor-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )

    other_contractor = Contractor(
        id=uuid.uuid4(),
        name="Other Plate Contractor",
        contractor_type="company",
        status="active",
    )

    other_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=other_contractor.id,
        user_id=other_contractor_user.id,
        is_active=True,
    )

    db_session.add(other_landlord_user)
    db_session.flush()

    db_session.add(other_landlord)
    db_session.flush()

    db_session.add(other_property)
    db_session.flush()

    db_session.add(other_contractor_user)
    db_session.add(other_contractor)
    db_session.flush()

    db_session.add(other_member)
    db_session.flush()

    existing = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=other_property.id,
        plate_id=context["plate"].id,
        contractor_id=other_contractor.id,
        contractor_member_id=other_member.id,
        assigned_by=context["assigning_employee"].id,
        status="in_progress",
    )

    db_session.add(existing)
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate already has an active installation assignment",
    ):
        service.create_assignment(
            property_id=context["property"].id,
            plate_id=context["plate"].id,
            contractor_id=context["contractor"].id,
            contractor_member_id=context["contractor_member"].id,
            assigned_by=context["assigning_employee"].id,
        )


def test_database_rejects_duplicate_active_property_assignment(db_session):
    from sqlalchemy.exc import IntegrityError

    context = create_assignment_context(db_session)

    first = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="assigned",
    )

    db_session.add(first)
    db_session.flush()

    second = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=uuid.uuid4(),
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="in_progress",
    )

    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_database_rejects_duplicate_active_plate_assignment(db_session):
    from sqlalchemy.exc import IntegrityError

    context = create_assignment_context(db_session)

    first = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="assigned",
    )

    db_session.add(first)
    db_session.flush()

    second_property = Property(
        id=uuid.uuid4(),
        landlord_id=context["property"].landlord_id,
        property_code=f"NEST-DB-PLATE-{uuid.uuid4().hex[:8].upper()}",
        name="Database Plate Constraint Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(second_property)
    db_session.flush()

    second = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=second_property.id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="submitted",
    )

    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_database_allows_new_active_assignment_after_completed_assignment(
    db_session,
):
    context = create_assignment_context(db_session)

    completed = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="completed",
    )

    db_session.add(completed)
    db_session.flush()

    active = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="assigned",
    )

    db_session.add(active)
    db_session.flush()

    assert active.id is not None
    assert active.status == "assigned"

def test_start_assignment_moves_assigned_to_in_progress(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    result = service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
    )

    assert result.id == assignment.id
    assert result.status == "in_progress"

    fetched = db_session.get(InstallationAssignment, assignment.id)

    assert fetched is not None
    assert fetched.status == "in_progress"




def test_submit_assignment_rejects_wrong_contractor_user(db_session):
    context = create_assignment_context(db_session)

    other_user = User(
        id=uuid.uuid4(),
        email=f"other-submitter-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
    )

    with pytest.raises(
        ValueError,
        match="Contractor user is not assigned to this installation",
    ):
        service.submit_assignment(
            assignment_id=assignment.id,
            contractor_user_id=other_user.id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=4.5,
            captured_at=datetime(2026, 9, 28, 18, 0, tzinfo=UTC),
        )

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)

    assert fetched_assignment is not None
    assert fetched_assignment.status == "in_progress"

def test_submit_assignment_rejects_user_whose_role_is_no_longer_contractor(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
    )

    context["contractor_user"].role = "landlord"
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Contractor member user must be a contractor",
    ):
        service.submit_assignment(
            assignment_id=assignment.id,
            contractor_user_id=context["contractor_user"].id,
            latitude=-1.2921,
            longitude=36.8219,
            accuracy_meters=4.5,
            captured_at=datetime(2026, 9, 28, 18, 0, tzinfo=UTC),
        )

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)

    assert fetched_assignment is not None
    assert fetched_assignment.status == "in_progress"


def test_submit_assignment_creates_installation_and_moves_to_submitted(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
    )

    captured_at = datetime(2026, 9, 28, 18, 0, tzinfo=UTC)

    installation = service.submit_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
        latitude=-1.2921,
        longitude=36.8219,
        accuracy_meters=4.5,
        captured_at=captured_at,
        notes="Plate installed and GPS evidence captured.",
    )

    assert installation.id is not None
    assert installation.property_id == context["property"].id
    assert installation.plate_id == context["plate"].id
    assert installation.assignment_id == assignment.id
    assert installation.installer_id == context["contractor_user"].id
    assert installation.latitude == -1.2921
    assert installation.longitude == 36.8219
    assert installation.accuracy_meters == 4.5
    assert installation.captured_at == captured_at
    assert installation.status == "submitted"
    assert installation.notes == "Plate installed and GPS evidence captured."

    fetched_assignment = db_session.get(InstallationAssignment, assignment.id)

    assert fetched_assignment is not None
    assert fetched_assignment.status == "submitted"

def test_start_assignment_requires_existing_assignment(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Installation assignment not found",
    ):
        service.start_assignment(
            assignment_id=uuid.uuid4(),
            contractor_user_id=context["contractor_user"].id,
        )


def test_start_assignment_requires_assigned_status(db_session):
    context = create_assignment_context(db_session)

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

    service = InstallationAssignmentService(db_session)

    with pytest.raises(
        ValueError,
        match="Installation assignment is not awaiting start",
    ):
        service.start_assignment(
            assignment_id=assignment.id,
            contractor_user_id=context["contractor_user"].id,
        )


def test_start_assignment_rejects_wrong_contractor_member(db_session):
    context = create_assignment_context(db_session)

    other_user = User(
        id=uuid.uuid4(),
        email=f"other-member-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )

    other_member = ContractorMember(
        id=uuid.uuid4(),
        contractor_id=context["contractor"].id,
        user_id=other_user.id,
        is_active=True,
    )

    db_session.add(other_user)
    db_session.flush()

    db_session.add(other_member)
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    with pytest.raises(
        ValueError,
        match="Contractor user is not assigned to this installation",
    ):
        service.start_assignment(
            assignment_id=assignment.id,
            contractor_user_id=other_user.id,
        )


def test_start_assignment_rejects_inactive_contractor_member(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    context["contractor_member"].is_active = False
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Contractor member is inactive",
    ):
        service.start_assignment(
            assignment_id=assignment.id,
            contractor_user_id=context["contractor_user"].id,
        )


def test_start_assignment_rejects_user_whose_role_is_no_longer_contractor(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    context["contractor_user"].role = "landlord"
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Contractor member user must be a contractor",
    ):
        service.start_assignment(
            assignment_id=assignment.id,
            contractor_user_id=context["contractor_user"].id,
        )


def test_start_assignment_rejects_inactive_contractor_member_user(db_session):
    context = create_assignment_context(db_session)

    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    context["contractor_user"].is_active = False
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Contractor member user is inactive",
    ):
        service.start_assignment(
            assignment_id=assignment.id,
            contractor_user_id=context["contractor_user"].id,
        )



def test_cancel_assignment_moves_assigned_to_cancelled(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    result = service.cancel_assignment(
        assignment_id=assignment.id,
        cancelled_by=context["assigning_employee"].id,
        reason="Contractor scheduling changed.",
    )

    assert result.id == assignment.id
    assert result.status == "cancelled"
    assert result.cancelled_by == context["assigning_employee"].id
    assert result.cancelled_at is not None
    assert result.cancellation_reason == "Contractor scheduling changed."


def test_cancel_assignment_moves_in_progress_to_cancelled(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
    )

    result = service.cancel_assignment(
        assignment_id=assignment.id,
        cancelled_by=context["assigning_employee"].id,
        reason="Operations reassigned this installation.",
    )

    assert result.status == "cancelled"
    assert result.cancellation_reason == "Operations reassigned this installation."


def test_cancel_assignment_moves_submitted_to_cancelled_without_removing_installation(db_session):
    from app.models.property_installation import PropertyInstallation

    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
    )

    installation = service.submit_assignment(
        assignment_id=assignment.id,
        contractor_user_id=context["contractor_user"].id,
        latitude=-1.2921,
        longitude=36.8219,
        accuracy_meters=4.5,
        captured_at=datetime(2026, 9, 28, 18, 0, tzinfo=UTC),
        notes="Installation evidence retained.",
    )

    result = service.cancel_assignment(
        assignment_id=assignment.id,
        cancelled_by=context["assigning_employee"].id,
        reason="Installation requires rework before verification.",
    )

    assert result.status == "cancelled"

    fetched_installation = db_session.get(PropertyInstallation, installation.id)
    assert fetched_installation is not None
    assert fetched_installation.assignment_id == assignment.id
    assert fetched_installation.status == "submitted"
    assert fetched_installation.notes == "Installation evidence retained."


def test_cancel_assignment_rejects_completed_assignment(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="completed",
    )
    db_session.add(assignment)
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Installation assignment cannot be cancelled",
    ):
        service.cancel_assignment(
            assignment_id=assignment.id,
            cancelled_by=context["assigning_employee"].id,
            reason="Attempted cancellation.",
        )


def test_cancel_assignment_rejects_already_cancelled_assignment(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="cancelled",
        cancelled_by=context["assigning_employee"].id,
        cancelled_at=datetime(2026, 9, 28, 17, 0, tzinfo=UTC),
        cancellation_reason="Already cancelled.",
    )
    db_session.add(assignment)
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Installation assignment cannot be cancelled",
    ):
        service.cancel_assignment(
            assignment_id=assignment.id,
            cancelled_by=context["assigning_employee"].id,
            reason="Second cancellation.",
        )


def test_cancel_assignment_requires_existing_employee(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    with pytest.raises(ValueError, match="Cancelling employee not found"):
        service.cancel_assignment(
            assignment_id=assignment.id,
            cancelled_by=uuid.uuid4(),
            reason="Cancellation reason.",
        )


def test_cancel_assignment_rejects_inactive_employee(db_session):
    context = create_assignment_context(db_session)
    context["assigning_employee"].is_active = False
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="assigned",
    )
    db_session.add(assignment)
    db_session.flush()

    with pytest.raises(ValueError, match="Cancelling employee is inactive"):
        service.cancel_assignment(
            assignment_id=assignment.id,
            cancelled_by=context["assigning_employee"].id,
            reason="Cancellation reason.",
        )


def test_cancel_assignment_requires_employee_actor(db_session):
    context = create_assignment_context(db_session)
    context["assigning_employee"].role = "landlord"
    db_session.flush()

    service = InstallationAssignmentService(db_session)

    assignment = InstallationAssignment(
        id=uuid.uuid4(),
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
        status="assigned",
    )
    db_session.add(assignment)
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Only Nestify employees can cancel installations",
    ):
        service.cancel_assignment(
            assignment_id=assignment.id,
            cancelled_by=context["assigning_employee"].id,
            reason="Cancellation reason.",
        )


def test_cancel_assignment_requires_reason(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    with pytest.raises(ValueError, match="Cancellation reason is required"):
        service.cancel_assignment(
            assignment_id=assignment.id,
            cancelled_by=context["assigning_employee"].id,
            reason="   ",
        )


def test_cancelled_assignment_releases_property_and_plate_for_new_assignment(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.cancel_assignment(
        assignment_id=assignment.id,
        cancelled_by=context["assigning_employee"].id,
        reason="Contractor became unavailable.",
    )

    replacement = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    assert replacement.id != assignment.id
    assert replacement.status == "assigned"

def test_list_assignments_returns_newest_first(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    first_assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    # The first assignment must be released before the same property/plate
    # can be used for another active assignment.
    service.cancel_assignment(
        assignment_id=first_assignment.id,
        cancelled_by=context["assigning_employee"].id,
        reason="Reassigning installation.",
    )

    second_assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    result = service.list_assignments()

    result_ids = [assignment.id for assignment in result]

    assert second_assignment.id in result_ids
    assert first_assignment.id in result_ids
    assert result_ids.index(second_assignment.id) < result_ids.index(first_assignment.id)


def test_list_assignments_filters_by_status(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    assignment = service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    service.cancel_assignment(
        assignment_id=assignment.id,
        cancelled_by=context["assigning_employee"].id,
        reason="Testing status filtering.",
    )

    assigned_results = service.list_assignments(status="assigned")
    cancelled_results = service.list_assignments(status="cancelled")

    assert all(item.status == "assigned" for item in assigned_results)
    assert all(item.status == "cancelled" for item in cancelled_results)
    assert assignment.id not in [item.id for item in assigned_results]
    assert assignment.id in [item.id for item in cancelled_results]


def test_list_assignments_unknown_status_returns_empty(db_session):
    context = create_assignment_context(db_session)
    service = InstallationAssignmentService(db_session)

    service.create_assignment(
        property_id=context["property"].id,
        plate_id=context["plate"].id,
        contractor_id=context["contractor"].id,
        contractor_member_id=context["contractor_member"].id,
        assigned_by=context["assigning_employee"].id,
    )

    result = service.list_assignments(status="not-a-real-status")

    assert result == []
