import uuid
from datetime import UTC, datetime

from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import AddressPlateLifecycleEvent
from app.models.address_plate_request import AddressPlateRequest
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.user import User
from app.services.address_plate_allocation_service import (
    AddressPlateAllocationService,
)
from app.services.address_plate_request_service import (
    AddressPlateRequestService,
)
from app.services.dispatch_service import DispatchService
from app.services.installation_assignment_service import (
    InstallationAssignmentService,
)
from app.services.manufacturing_order_service import ManufacturingOrderService
from app.services.property_activation_service import PropertyActivationService
from app.services.property_installation_verification_service import (
    PropertyInstallationVerificationService,
)
from app.services.property_verification_service import PropertyVerificationService


def test_plate_to_property_activation_flow(db_session):
    # ---------------------------------------------------------
    # Actors
    # ---------------------------------------------------------
    landlord_user = User(
        email=f"golden-landlord-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(landlord_user)
    db_session.flush()

    landlord = Landlord(
        user_id=landlord_user.id,
        display_name="Golden Path Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    plate_employee = User(
        email=f"golden-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )
    db_session.add(plate_employee)
    db_session.flush()

    verification_employee = User(
        email=f"golden-verifier-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )
    db_session.add(verification_employee)
    db_session.flush()

    contractor = Contractor(
        name="Golden Path Contractor",
        contractor_type="company",
        status="active",
    )
    db_session.add(contractor)
    db_session.flush()

    contractor_user = User(
        email=f"golden-contractor-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="contractor",
        is_active=True,
    )
    db_session.add(contractor_user)
    db_session.flush()

    contractor_member = ContractorMember(
        contractor_id=contractor.id,
        user_id=contractor_user.id,
        is_active=True,
    )
    db_session.add(contractor_member)
    db_session.flush()

    # ---------------------------------------------------------
    # Property onboarding state required by the physical loop
    # ---------------------------------------------------------
    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Golden Path Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Golden Path Property, Nairobi",
        county="Nairobi",
        sub_county="Westlands",
        locality="Westlands",
    )
    db_session.add(address)
    db_session.flush()

    verification_service = PropertyVerificationService(db_session)

    verification = verification_service.verify_property(
        property_id=property.id,
        verified_by=plate_employee.id,
        status="verified",
        notes="Golden-path property verification",
    )

    assert verification.status == "verified"

    db_session.refresh(property)
    assert property.status == "verified"

    # ---------------------------------------------------------
    # Plate request
    # ---------------------------------------------------------
    request_service = AddressPlateRequestService(db_session)

    plate_request = request_service.create_request(
        property_id=property.id,
        requested_by=landlord_user.id,
    )

    assert plate_request.status == "pending"

    plate_request = request_service.approve_request(
        request_id=plate_request.id,
    )

    assert plate_request.status == "approved"

    # ---------------------------------------------------------
    # Manufacturing
    # ---------------------------------------------------------
    manufacturing_service = ManufacturingOrderService(db_session)

    order = manufacturing_service.create_order(
        quantity=1,
        created_by=plate_employee.id,
    )

    assert order.status == "draft"

    order = manufacturing_service.approve_order(
        order_code=order.order_code,
        approved_by=plate_employee.id,
    )

    assert order.status == "approved"

    order = manufacturing_service.start_order(
        order_code=order.order_code,
    )

    assert order.status == "in_production"

    order = manufacturing_service.complete_order(
        order_code=order.order_code,
        completed_by=plate_employee.id,
    )

    assert order.status == "completed"

    manufactured_plates = manufacturing_service.get_order_plates(
        order.order_code
    )

    assert len(manufactured_plates) == 1

    plate = manufactured_plates[0]

    db_session.refresh(plate)

    assert plate.property_id is None
    assert plate.status == "unactivated"

    manufactured_event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
            AddressPlateLifecycleEvent.event_type == "manufactured",
        )
        .one()
    )

    assert manufactured_event.plate_id == plate.id

    # ---------------------------------------------------------
    # Allocation
    # ---------------------------------------------------------
    allocation_service = AddressPlateAllocationService(db_session)

    plate = allocation_service.allocate_plate(
        request_id=plate_request.id,
        performed_by=plate_employee.id,
    )

    assert plate.property_id == property.id

    allocation_event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
            AddressPlateLifecycleEvent.event_type == "allocated",
        )
        .one()
    )

    assert allocation_event.plate_id == plate.id

    db_session.refresh(plate)
    assert plate.property_id == property.id

    db_session.refresh(plate_request)
    assert plate_request.status == "fulfilled"

    # ---------------------------------------------------------
    # Dispatch
    # ---------------------------------------------------------
    dispatch_service = DispatchService(db_session)

    dispatch = dispatch_service.create_dispatch(
        plate_ids=[plate.id],
        destination="Golden Path Property, Nairobi",
        recipient_name="Golden Path Landlord",
        recipient_phone="+254700000001",
        created_by=plate_employee.id,
        tracking_reference=f"TRK-{uuid.uuid4().hex[:10].upper()}",
    )

    assert dispatch.status == "draft"

    dispatch = dispatch_service.mark_ready(
        dispatch_code=dispatch.dispatch_code,
    )

    assert dispatch.status == "ready"

    dispatch = dispatch_service.mark_dispatched(
        dispatch_code=dispatch.dispatch_code,
        performed_by=plate_employee.id,
    )

    assert dispatch.status == "dispatched"

    dispatch = dispatch_service.mark_delivered(
        dispatch_code=dispatch.dispatch_code,
    )

    assert dispatch.status == "delivered"

    # ---------------------------------------------------------
    # Installation assignment
    # ---------------------------------------------------------
    assignment_service = InstallationAssignmentService(db_session)

    assignment = assignment_service.create_assignment(
        property_id=property.id,
        plate_id=plate.id,
        contractor_id=contractor.id,
        contractor_member_id=contractor_member.id,
        assigned_by=plate_employee.id,
        due_at=datetime(2026, 10, 5, 12, 0, tzinfo=UTC),
    )

    assert assignment.status == "assigned"

    assignment = assignment_service.start_assignment(
        assignment_id=assignment.id,
        contractor_user_id=contractor_user.id,
    )

    assert assignment.status == "in_progress"

    installation = assignment_service.submit_assignment(
        assignment_id=assignment.id,
        contractor_user_id=contractor_user.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        notes="Plate physically installed at the property.",
    )

    assert installation.status == "submitted"
    assert installation.property_id == property.id
    assert installation.plate_id == plate.id
    assert installation.assignment_id == assignment.id
    assert installation.installer_id == contractor_user.id

    db_session.refresh(assignment)
    assert assignment.status == "submitted"

    # ---------------------------------------------------------
    # Installation verification
    # ---------------------------------------------------------
    installation_verification_service = (
        PropertyInstallationVerificationService(db_session)
    )

    installation_verification = (
        installation_verification_service.verify_installation(
            property_id=property.id,
            installation_id=installation.id,
            verified_by=verification_employee.id,
            status="verified",
            notes="Installation verified.",
        )
    )

    assert installation_verification.status == "verified"

    db_session.refresh(installation)
    db_session.refresh(assignment)

    assert installation.status == "verified"
    assert assignment.status == "completed"

    # Verification produces both physical lifecycle events.
    installed_event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
            AddressPlateLifecycleEvent.event_type == "installed",
        )
        .one()
    )

    verified_event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
            AddressPlateLifecycleEvent.event_type == "verified",
        )
        .one()
    )

    assert installed_event.plate_id == plate.id
    assert verified_event.plate_id == plate.id

    # ---------------------------------------------------------
    # Property activation
    # ---------------------------------------------------------
    activation_service = PropertyActivationService(db_session)

    activated_plate = activation_service.activate_property(
        property_id=property.id,
        plate_code=plate.plate_code,
        activated_by=verification_employee.id,
    )

    assert activated_plate.id == plate.id
    assert activated_plate.property_id == property.id

    db_session.refresh(property)
    db_session.refresh(activated_plate)

    assert property.status == "active"
    assert activated_plate.status == "active"

    activation_event = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
            AddressPlateLifecycleEvent.event_type == "activated",
        )
        .one()
    )

    assert activation_event.plate_id == plate.id

    # ---------------------------------------------------------
    # Final system-level invariants
    # ---------------------------------------------------------
    lifecycle_events = (
        db_session.query(AddressPlateLifecycleEvent)
        .filter(
            AddressPlateLifecycleEvent.plate_id == plate.id,
        )
        .order_by(AddressPlateLifecycleEvent.created_at.asc())
        .all()
    )

    assert [event.event_type for event in lifecycle_events] == [
        "manufactured",
        "allocated",
        "dispatched",
        "installed",
        "verified",
        "activated",
    ]

    assert plate.property_id == property.id
    assert plate.status == "active"
    assert property.status == "active"
