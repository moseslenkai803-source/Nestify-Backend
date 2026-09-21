import uuid

import pytest

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.address_plate_service import AddressPlateService


def test_create_plate_creates_unactivated_plate(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()

    assert plate.id is not None
    assert plate.plate_code.startswith("PLATE-")
    assert plate.status == "unactivated"
    assert plate.property_id is None
    assert plate.activated_at is None
    assert plate.verified_at is None


def test_get_plate_by_code_returns_existing_plate(db_session):
    service = AddressPlateService(db_session)

    created_plate = service.create_plate()

    found_plate = service.get_plate_by_code(
        created_plate.plate_code
    )

    assert found_plate is not None
    assert found_plate.id == created_plate.id
    assert found_plate.plate_code == created_plate.plate_code


def test_verify_plate_changes_status_and_sets_verified_at(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()

    verified_plate = service.verify_plate(
        plate.plate_code
    )

    assert verified_plate.id == plate.id
    assert verified_plate.status == "verified"
    assert verified_plate.verified_at is not None


def test_link_verified_plate_to_property_activates_plate(db_session):
    user = User(
        email=f"plate-link-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Plate Link Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Plate Link Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateService(db_session)

    plate = service.create_plate()

    service.verify_plate(plate.plate_code)

    activated_plate = service.link_plate_to_property(
        plate_code=plate.plate_code,
        property_id=property.id,
    )

    assert activated_plate.id == plate.id
    assert activated_plate.property_id == property.id
    assert activated_plate.status == "active"
    assert activated_plate.verified_at is not None
    assert activated_plate.activated_at is not None


def test_unverified_plate_cannot_be_linked_to_property(db_session):
    user = User(
        email=f"plate-unverified-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Unverified Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Unverified Plate Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateService(db_session)

    plate = service.create_plate()

    with pytest.raises(
        ValueError,
        match="Only verified plates can be linked to a property",
    ):
        service.link_plate_to_property(
            plate_code=plate.plate_code,
            property_id=property.id,
        )


def test_link_plate_raises_when_property_does_not_exist(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()
    service.verify_plate(plate.plate_code)

    with pytest.raises(
        ValueError,
        match="Property not found",
    ):
        service.link_plate_to_property(
            plate_code=plate.plate_code,
            property_id=uuid.uuid4(),
        )


def test_plate_cannot_be_linked_twice(db_session):
    user = User(
        email=f"plate-twice-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Double Link Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Double Link Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateService(db_session)

    plate = service.create_plate()
    service.verify_plate(plate.plate_code)

    service.link_plate_to_property(
        plate_code=plate.plate_code,
        property_id=property.id,
    )

    with pytest.raises(
        ValueError,
        match="Plate is already linked to a property",
    ):
        service.link_plate_to_property(
            plate_code=plate.plate_code,
            property_id=property.id,
        )


def test_verified_plate_cannot_be_verified_again(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()

    service.verify_plate(plate.plate_code)

    with pytest.raises(
        ValueError,
        match="Plate cannot be verified in its current status",
    ):
        service.verify_plate(plate.plate_code)


def test_active_plate_cannot_be_verified_again(db_session):
    user = User(
        email=f"plate-active-verify-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Active Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Active Plate Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateService(db_session)

    plate = service.create_plate()
    service.verify_plate(plate.plate_code)

    service.link_plate_to_property(
        plate_code=plate.plate_code,
        property_id=property.id,
    )

    with pytest.raises(
        ValueError,
        match="Plate cannot be verified in its current status",
    ):
        service.verify_plate(plate.plate_code)


def test_active_plate_cannot_be_linked_to_another_property(db_session):
    user = User(
        email=f"plate-relink-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Relink Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property_one = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="First Property",
        property_type="residential",
        status="draft",
    )
    property_two = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Second Property",
        property_type="residential",
        status="draft",
    )

    db_session.add_all([property_one, property_two])
    db_session.flush()

    service = AddressPlateService(db_session)

    plate = service.create_plate()
    service.verify_plate(plate.plate_code)

    service.link_plate_to_property(
        plate_code=plate.plate_code,
        property_id=property_one.id,
    )

    with pytest.raises(
        ValueError,
        match="Plate is already linked to a property",
    ):
        service.link_plate_to_property(
            plate_code=plate.plate_code,
            property_id=property_two.id,
        )


def test_property_cannot_have_two_primary_plates(db_session):
    user = User(
        email=f"plate-property-twice-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Two Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Single Plate Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = AddressPlateService(db_session)

    first_plate = service.create_plate()
    service.verify_plate(first_plate.plate_code)
    service.link_plate_to_property(
        plate_code=first_plate.plate_code,
        property_id=property.id,
    )

    second_plate = service.create_plate()
    service.verify_plate(second_plate.plate_code)

    with pytest.raises(
        ValueError,
        match="Property already has a primary address plate",
    ):
        service.link_plate_to_property(
            plate_code=second_plate.plate_code,
            property_id=property.id,
        )
