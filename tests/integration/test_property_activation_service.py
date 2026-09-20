import uuid

import pytest

from app.models.landlord import Landlord
from app.models.property_address import PropertyAddress
from app.models.user import User
from app.services.address_plate_service import AddressPlateService
from app.services.property_activation_service import PropertyActivationService
from app.services.property_service import PropertyService


def test_activate_property_links_verified_plate_to_property(db_session):
    user = User(
        email=f"activation-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
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

    plate_service = AddressPlateService(db_session)

    plate = plate_service.create_plate()

    plate_service.verify_plate(
        plate_code=plate.plate_code,
    )

    activation_service = PropertyActivationService(db_session)

    activated_plate = activation_service.activate_property(
        property_id=property.id,
        landlord_id=landlord.id,
        plate_code=plate.plate_code,
    )

    assert activated_plate.id == plate.id
    assert activated_plate.property_id == property.id
    assert activated_plate.status == "active"
    assert activated_plate.activated_at is not None
    assert property.status == "active"


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

    plate_service = AddressPlateService(db_session)

    plate = plate_service.create_plate()

    plate_service.verify_plate(
        plate_code=plate.plate_code,
    )

    activation_service = PropertyActivationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property must have an address before activation",
    ):
        activation_service.activate_property(
            property_id=property.id,
            landlord_id=landlord.id,
            plate_code=plate.plate_code,
        )
