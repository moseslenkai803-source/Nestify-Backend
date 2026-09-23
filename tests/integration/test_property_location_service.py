import uuid
from datetime import UTC, datetime

import pytest

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.property_location_service import PropertyLocationService


def create_test_property(db_session):
    user = User(
        email=f"location-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Location Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Location Service Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    return property


def test_create_location_creates_property_location(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    captured_at = datetime.now(UTC)

    location = service.create_location(
        property_id=property.id,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=captured_at,
        accuracy_meters=12.5,
    )

    assert location.id is not None
    assert location.property_id == property.id
    assert location.latitude == -1.2921
    assert location.longitude == 36.8219
    assert location.source == "device_gps"
    assert location.capture_method == "user_confirmed_device_location"
    assert location.accuracy_meters == 12.5
    assert location.captured_at == captured_at
    assert location.status == "unverified"
    assert location.location is not None


def test_create_location_raises_when_property_does_not_exist(db_session):
    service = PropertyLocationService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.create_location(
            property_id=uuid.uuid4(),
            latitude=-1.2921,
            longitude=36.8219,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
        )


def test_create_location_raises_when_property_already_has_location(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    service.create_location(
        property_id=property.id,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
    )

    with pytest.raises(
        ValueError,
        match="Property already has a location",
    ):
        service.create_location(
            property_id=property.id,
            latitude=-1.3000,
            longitude=36.8300,
            source="landlord_provided",
            capture_method="manual_entry",
            captured_at=datetime.now(UTC),
        )


def test_create_location_raises_for_invalid_latitude(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Latitude must be between -90 and 90",
    ):
        service.create_location(
            property_id=property.id,
            latitude=91,
            longitude=36.8219,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
        )


def test_create_location_raises_for_invalid_longitude(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Longitude must be between -180 and 180",
    ):
        service.create_location(
            property_id=property.id,
            latitude=-1.2921,
            longitude=181,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
        )


def test_create_location_raises_for_negative_accuracy(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Accuracy must be greater than or equal to 0",
    ):
        service.create_location(
            property_id=property.id,
            latitude=-1.2921,
            longitude=36.8219,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
            accuracy_meters=-1,
        )


def test_get_location_returns_property_location(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    created_location = service.create_location(
        property_id=property.id,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
        accuracy_meters=12.5,
    )

    location = service.get_location(property.id)

    assert location.id == created_location.id
    assert location.property_id == property.id
    assert location.latitude == -1.2921
    assert location.longitude == 36.8219
    assert location.source == "device_gps"
    assert location.status == "unverified"


def test_get_location_raises_when_location_does_not_exist(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property location not found",
    ):
        service.get_location(property.id)
