import uuid
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
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


def test_create_address_serializes_concurrent_creations_for_same_property(
    db_session,
):
    user = User(
        email=f"concurrent-address-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Concurrent Address Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Concurrent Address Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    property_id = property.id
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    second_started = Event()
    second_finished = Event()
    second_error = {}
    thread = None

    try:
        first_service = PropertyAddressService(first_session)

        locked_property = (
            first_service.property_repository.get_by_id_for_update(
                property_id
            )
        )

        assert locked_property is not None

        def create_from_second_transaction():
            try:
                second_service = PropertyAddressService(second_session)
                second_started.set()

                second_service.create_address(
                    property_id=property_id,
                    formatted_address="Second Address, Nairobi",
                    county="Nairobi",
                    latitude=-1.3000,
                    longitude=36.8300,
                )
            except Exception as exc:
                second_error["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=create_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_address = first_service.create_address(
            property_id=property_id,
            formatted_address="First Address, Nairobi",
            county="Nairobi",
            latitude=-1.2921,
            longitude=36.8219,
        )

        assert first_address.property_id == property_id

        first_session.commit()

        assert second_finished.wait(timeout=2)
        thread.join(timeout=2)

        assert isinstance(second_error.get("error"), ValueError)
        assert str(second_error["error"]) == (
            "Property already has an address"
        )

        second_session.rollback()

        addresses = (
            second_session.query(PropertyAddress)
            .filter(PropertyAddress.property_id == property_id)
            .all()
        )

        assert len(addresses) == 1
        assert addresses[0].formatted_address == "First Address, Nairobi"

    finally:
        if thread is not None:
            thread.join(timeout=2)
        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()
