import uuid
from datetime import UTC, datetime

import pytest

from app.models.landlord import Landlord
from app.models.address_plate import AddressPlate
from app.models.property_address import PropertyAddress
from app.models.user import User
from app.services.address_plate_lifecycle_service import AddressPlateLifecycleService
from app.services.address_plate_service import AddressPlateService
from app.services.property_activation_service import PropertyActivationService
from app.services.property_service import PropertyService


def test_activate_property_activates_verified_plate(db_session):
    user = User(
        email=f"activation-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Activation Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_service = PropertyService(db_session)

    property = property_service.create_property(
        landlord_id=landlord.id,
        name="Activation Test Property",
        property_type="residential",
    )

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Activation Test Address",
    )
    db_session.add(address)
    db_session.flush()

    employee = User(
        email=f"activation-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )
    reviewer = User(
        email=f"activation-reviewer-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="installation_verification",
        is_active=True,
    )
    db_session.add(employee)
    db_session.add(reviewer)
    db_session.flush()

    plate_service = AddressPlateService(db_session)
    db_session.query(AddressPlate).filter(
        AddressPlate.status == "unactivated",
        AddressPlate.property_id.is_(None),
    ).update(
        {"status": "verified"},
        synchronize_session="fetch",
    )

    plate = plate_service.create_plate()

    lifecycle_service = AddressPlateLifecycleService(db_session)

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=employee.id,
    )

    from app.services.address_plate_request_service import (
        AddressPlateRequestService,
    )
    from app.services.address_plate_allocation_service import (
        AddressPlateAllocationService,
    )

    request_service = AddressPlateRequestService(db_session)
    request = request_service.create_request(
        property_id=property.id,
        requested_by=user.id,
    )
    request_service.approve_request(request.id)

    allocation_service = AddressPlateAllocationService(db_session)
    allocation_service.allocate_plate(
        request_id=request.id,
        performed_by=employee.id,
    )

    from app.services.dispatch_service import DispatchService

    dispatch_service = DispatchService(db_session)
    dispatch = dispatch_service.create_dispatch(
        plate_ids=[plate.id],
        destination="Activation Test Address",
        recipient_name="Activation Test Landlord",
        recipient_phone="+254700000000",
        created_by=employee.id,
    )

    dispatch_service.mark_ready(dispatch.dispatch_code)
    dispatch_service.mark_dispatched(
        dispatch_code=dispatch.dispatch_code,
        performed_by=employee.id,
    )

    from app.services.property_installation_service import (
        PropertyInstallationService,
    )

    installation_service = PropertyInstallationService(db_session)
    installation = installation_service.create_installation(
        property_id=property.id,
        plate_id=plate.id,
        installer_id=employee.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
    )

    from app.services.property_installation_verification_service import (
        PropertyInstallationVerificationService,
    )

    verification_service = PropertyInstallationVerificationService(
        db_session
    )
    verification_service.verify_installation(
        property_id=property.id,
        installation_id=installation.id,
        verified_by=reviewer.id,
        status="verified",
        notes="Installation confirmed",
    )

    property.status = "verified"
    db_session.flush()

    activation_service = PropertyActivationService(db_session)

    activated_plate = activation_service.activate_property(
        property_id=property.id,
        plate_code=plate.plate_code,
    )

    assert activated_plate.id == plate.id
    assert activated_plate.property_id == property.id
    assert activated_plate.status == "active"
    assert activated_plate.activated_at is not None
    assert property.status == "active"

    latest_event = lifecycle_service.get_latest_event(plate.id)

    assert latest_event is not None
    assert latest_event.event_type == "activated"
    assert latest_event.performed_by == reviewer.id


def test_activate_property_requires_address(db_session):
    user = User(
        email=f"activation-no-address-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="No Address Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_service = PropertyService(db_session)

    property = property_service.create_property(
        landlord_id=landlord.id,
        name="Property Without Address",
        property_type="residential",
    )

    property.status = "verified"
    db_session.flush()

    activation_service = PropertyActivationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property must have an address before activation",
    ):
        activation_service.activate_property(
            property_id=property.id,
            plate_code="PLATE-DOES-NOT-MATTER",
        )



def test_activate_property_rejects_missing_property(db_session):
    activation_service = PropertyActivationService(db_session)

    missing_property_id = uuid.uuid4()

    with pytest.raises(
        ValueError,
        match="Property not found",
    ):
        activation_service.activate_property(
            property_id=missing_property_id,
            plate_code="PLATE-DOES-NOT-MATTER",
        )

def test_activate_property_requires_verified_property(db_session):
    user = User(
        email=f"activation-unverified-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Unverified Activation Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_service = PropertyService(db_session)

    property = property_service.create_property(
        landlord_id=landlord.id,
        name="Unverified Activation Property",
        property_type="residential",
    )

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Unverified Activation Address",
    )
    db_session.add(address)
    db_session.flush()

    activation_service = PropertyActivationService(db_session)

    with pytest.raises(
        ValueError,
        match="Only verified properties can be activated",
    ):
        activation_service.activate_property(
            property_id=property.id,
            plate_code="PLATE-DOES-NOT-MATTER",
        )

    db_session.refresh(property)

    assert property.status == "draft"


def test_activate_property_rejects_already_active_property(db_session):
    user = User(
        email=f"activation-active-property-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Already Active Property Landlord",
        phone="+254700000002",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_service = PropertyService(db_session)

    property = property_service.create_property(
        landlord_id=landlord.id,
        name="Already Active Property",
        property_type="residential",
    )

    property.status = "active"
    db_session.flush()

    activation_service = PropertyActivationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property is already active",
    ):
        activation_service.activate_property(
            property_id=property.id,
            plate_code="PLATE-DOES-NOT-MATTER",
        )

    db_session.refresh(property)

    assert property.status == "active"
