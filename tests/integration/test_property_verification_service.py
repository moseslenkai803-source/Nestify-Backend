import uuid

import pytest

from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.user import User
 
from app.services.property_verification_service import PropertyVerificationService


def create_verified_property(db_session):
    employee = User(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

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
        display_name="Verification Service Landlord",
        phone="+254700000020",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Verification Service Property",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="active",
    )

    db_session.add(employee)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    return employee, property_record, plate


def add_property_address(db_session, property_id):
    address = PropertyAddress(
        id=uuid.uuid4(),
        property_id=property_id,
        formatted_address="123 Verification Street, Nairobi, Kenya",
        county="Nairobi",
        sub_county="Westlands",
        locality="Nairobi",
        latitude=-1.286389,
        longitude=36.817223,
    )

    db_session.add(address)
    db_session.flush()
    return address


def test_verify_property_creates_verified_record_and_updates_property(
    db_session,
):
    employee, property_record, _ = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    result = service.verify_property(
        property_id=property_record.id,
        verified_by=employee.id,
        status="verified",
        notes="All required information verified",
    )

    assert result.property_id == property_record.id
    assert result.verified_by == employee.id
    assert result.status == "verified"
    assert result.notes == "All required information verified"
    assert result.verified_at is not None
    assert property_record.status == "verified"


def test_rejected_property_verification_preserves_property_status(
    db_session,
):
    employee, property_record, _ = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    result = service.verify_property(
        property_id=property_record.id,
        verified_by=employee.id,
        status="rejected",
        notes="Additional information required",
    )

    assert result.status == "rejected"
    assert result.notes == "Additional information required"
    assert property_record.status == "draft"


def test_verify_property_requires_existing_property(db_session):
    employee = User(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    service = PropertyVerificationService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.verify_property(
            property_id=uuid.uuid4(),
            verified_by=employee.id,
            status="verified",
        )


def test_verify_property_requires_address(db_session):
    employee, property_record, _ = create_verified_property(db_session)

    service = PropertyVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property must have an address before verification",
    ):
        service.verify_property(
            property_id=property_record.id,
            verified_by=employee.id,
            status="verified",
        )


def test_verify_property_requires_active_address_plate(db_session):
    employee, property_record, plate = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    plate.status = "verified"
    db_session.flush()

    service = PropertyVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property must have an active address plate before verification",
    ):
        service.verify_property(
            property_id=property_record.id,
            verified_by=employee.id,
            status="verified",
        )


def test_verify_property_rejects_invalid_status(db_session):
    employee, property_record, _ = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Verification status must be 'verified' or 'rejected'",
    ):
        service.verify_property(
            property_id=property_record.id,
            verified_by=employee.id,
            status="pending",
        )
