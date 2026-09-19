import uuid

import pytest

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.property_address_service import PropertyAddressService


def test_create_address_creates_property_address(db_session):
    user = User(
        email=f"address-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Address Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Address Service Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = PropertyAddressService(db_session)

    address = service.create_address(
        property_id=property.id,
        formatted_address="123 Test Road, Nairobi",
        county="Nairobi",
        sub_county="Westlands",
        locality="Westlands",
        latitude=-1.2921,
        longitude=36.8219,
    )

    assert address.id is not None
    assert address.property_id == property.id
    assert address.formatted_address == "123 Test Road, Nairobi"
    assert address.county == "Nairobi"
    assert address.latitude == -1.2921
    assert address.longitude == 36.8219
    assert address.location is not None


def test_create_address_raises_when_property_does_not_exist(db_session):
    service = PropertyAddressService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.create_address(
            property_id=uuid.uuid4(),
            formatted_address="Invalid Property Address",
        )


def test_create_address_raises_when_property_already_has_address(db_session):
    user = User(
        email=f"duplicate-address-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Duplicate Address Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Duplicate Address Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    service = PropertyAddressService(db_session)

    service.create_address(
        property_id=property.id,
        formatted_address="First Address, Nairobi",
        county="Nairobi",
        latitude=-1.2921,
        longitude=36.8219,
    )

    with pytest.raises(
        ValueError,
        match="Property already has an address",
    ):
        service.create_address(
            property_id=property.id,
            formatted_address="Second Address, Nairobi",
            county="Nairobi",
            latitude=-1.3000,
            longitude=36.8300,
        )
