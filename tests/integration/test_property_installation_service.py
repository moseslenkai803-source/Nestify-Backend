import uuid
from datetime import UTC, datetime

import pytest

from app.models.address_plate import AddressPlate
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.property_installation_service import (
    PropertyInstallationService,
)


def create_installation_context(db_session):
    landlord_user = User(
        id=uuid.uuid4(),
        email=f"landlord-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    installer = User(
        id=uuid.uuid4(),
        email=f"installer-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Installation Service Landlord",
        phone="+254700000030",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Installation Service Property",
        property_type="residential",
        status="verified",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
        property_id=property_record.id,
    )

    db_session.add(landlord_user)
    db_session.add(installer)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    lifecycle_service = AddressPlateLifecycleService(db_session)

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="manufactured",
        performed_by=installer.id,
    )

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="allocated",
        performed_by=installer.id,
    )

    lifecycle_service.record_event(
        plate_id=plate.id,
        event_type="dispatched",
        performed_by=installer.id,
    )

    return landlord_user, installer, property_record, plate


def test_create_installation_creates_submitted_record(db_session):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    captured_at = datetime.now(UTC)

    result = service.create_installation(
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=captured_at,
        notes="Plate installed at main entrance",
    )

    assert result.property_id == property_record.id
    assert result.plate_id == plate.id
    assert result.installer_id == installer.id
    assert result.latitude == -1.286389
    assert result.longitude == 36.817223
    assert result.accuracy_meters == 5.0
    assert result.captured_at == captured_at
    assert result.status == "submitted"
    assert result.notes == "Plate installed at main entrance"
    assert result.created_at is not None
    assert result.updated_at is not None

    lifecycle_service = AddressPlateLifecycleService(db_session)

    latest_event = lifecycle_service.get_latest_event(plate.id)

    assert latest_event is not None
    assert latest_event.event_type == "dispatched"
    assert latest_event.performed_by == installer.id


def test_create_installation_requires_existing_property(db_session):
    _, installer, _, plate = create_installation_context(db_session)

    service = PropertyInstallationService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.create_installation(
            property_id=uuid.uuid4(),
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_requires_existing_plate(db_session):
    _, installer, property_record, _ = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    with pytest.raises(ValueError, match="Address plate not found"):
        service.create_installation(
            property_id=property_record.id,
            plate_id=uuid.uuid4(),
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_requires_existing_installer(db_session):
    _, _, property_record, plate = create_installation_context(db_session)

    service = PropertyInstallationService(db_session)

    with pytest.raises(ValueError, match="Installer not found"):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=uuid.uuid4(),
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_rejects_inactive_installer(db_session):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    installer.is_active = False
    db_session.flush()

    service = PropertyInstallationService(db_session)

    with pytest.raises(ValueError, match="Installer is inactive"):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_requires_plate_linked_to_property(db_session):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

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
        display_name="Other Installation Landlord",
        phone="+254700000031",
        landlord_type="individual",
    )

    other_property = Property(
        id=uuid.uuid4(),
        landlord_id=other_landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Other Installation Property",
        property_type="residential",
        status="verified",
    )

    db_session.add(other_landlord_user)
    db_session.flush()

    db_session.add(other_landlord)
    db_session.flush()

    db_session.add(other_property)
    db_session.flush()

    plate.property_id = other_property.id
    db_session.flush()

    service = PropertyInstallationService(db_session)

    with pytest.raises(
        ValueError,
        match="Address plate is not linked to this property",
    ):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


@pytest.mark.parametrize("latitude", [-90.1, 90.1])
def test_create_installation_rejects_invalid_latitude(
    db_session,
    latitude,
):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    with pytest.raises(
        ValueError,
        match="Latitude must be between -90 and 90",
    ):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=latitude,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


@pytest.mark.parametrize("longitude", [-180.1, 180.1])
def test_create_installation_rejects_invalid_longitude(
    db_session,
    longitude,
):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    with pytest.raises(
        ValueError,
        match="Longitude must be between -180 and 180",
    ):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=longitude,
            accuracy_meters=5.0,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_rejects_negative_accuracy(db_session):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    with pytest.raises(
        ValueError,
        match="Accuracy must be greater than or equal to 0",
    ):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=-1,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_requires_timezone_aware_timestamp(db_session):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    with pytest.raises(
        ValueError,
        match="Captured timestamp must be timezone-aware",
    ):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286389,
            longitude=36.817223,
            accuracy_meters=5.0,
            captured_at=datetime(2026, 9, 23, 12, 0, 0),
        )


def test_create_installation_rejects_duplicate_submitted_installation(
    db_session,
):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    service = PropertyInstallationService(db_session)

    service.create_installation(
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
    )

    with pytest.raises(
        ValueError,
        match="Property already has a submitted installation",
    ):
        service.create_installation(
            property_id=property_record.id,
            plate_id=plate.id,
            installer_id=installer.id,
            latitude=-1.286390,
            longitude=36.817224,
            accuracy_meters=4.0,
            captured_at=datetime.now(UTC),
        )


def test_create_installation_allows_new_submission_after_rejected_installation(
    db_session,
):
    _, installer, property_record, plate = create_installation_context(
        db_session
    )

    from app.models.property_installation import PropertyInstallation

    rejected_installation = PropertyInstallation(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=installer.id,
        latitude=-1.286389,
        longitude=36.817223,
        accuracy_meters=5.0,
        captured_at=datetime.now(UTC),
        status="rejected",
        notes="GPS position did not match expected location",
    )

    db_session.add(rejected_installation)
    db_session.flush()

    service = PropertyInstallationService(db_session)

    result = service.create_installation(
        property_id=property_record.id,
        plate_id=plate.id,
        installer_id=installer.id,
        latitude=-1.286390,
        longitude=36.817224,
        accuracy_meters=4.0,
        captured_at=datetime.now(UTC),
    )

    assert result.status == "submitted"
    assert result.property_id == property_record.id
    assert result.plate_id == plate.id
