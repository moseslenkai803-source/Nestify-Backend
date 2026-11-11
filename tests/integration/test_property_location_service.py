import uuid
from datetime import UTC, datetime
from threading import Event, Thread
from time import monotonic

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, engine
from app.models.employee import Employee
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_location import PropertyLocation
from app.models.property_location_verification import (
    PropertyLocationVerification,
)
from app.repositories.property_location_repository import (
    PropertyLocationRepository,
)
from app.models.property_access import PropertyAccess
from app.models.user import User
from app.core.property_actions import PropertyAction
from app.services.property_location_service import (
    LocationSubmissionConflict,
    PropertyLocationService,
)


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


def submit_location(db_session, service, property, **location_data):
    landlord = db_session.get(Landlord, property.landlord_id)
    return submit_as(service, property, landlord.user_id, **location_data)


def submit_as(service, property, user_id, **location_data):
    return service.create_location(
        property_id=property.id,
        submitted_by_id=user_id,
        **location_data,
    )


def create_employee(db_session, active=True, terminated=False):
    user = User(
        email=f"location-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=active,
    )
    db_session.add(user)
    db_session.flush()
    employee = Employee(
        user_id=user.id,
        employee_number=f"EMP-{uuid.uuid4().hex[:12]}",
        department="property",
        position="manager",
        ended_at=datetime.now(UTC) if terminated else None,
    )
    db_session.add(employee)
    db_session.flush()
    return user, employee


def create_location_payload():
    return {
        "latitude": -1.2921,
        "longitude": 36.8219,
        "source": "device_gps",
        "capture_method": "user_confirmed_device_location",
        "captured_at": datetime.now(UTC),
    }


def test_create_location_creates_property_location(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    captured_at = datetime.now(UTC)

    submitted_at_before = datetime.now(UTC)
    location = submit_location(
        db_session,
        service,
        property,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=captured_at,
        accuracy_meters=12.5,
    )
    submitted_at_after = datetime.now(UTC)

    assert location.id is not None
    assert location.property_id == property.id
    assert location.latitude == -1.2921
    assert location.longitude == 36.8219
    assert location.source == "device_gps"
    assert location.capture_method == "user_confirmed_device_location"
    assert location.accuracy_meters == 12.5
    assert location.captured_at == captured_at
    assert location.version_number == 1
    assert location.submitted_by_id == db_session.get(
        Landlord, property.landlord_id
    ).user_id
    assert location.submitted_at is not None
    assert location.submitted_at >= submitted_at_before
    assert location.submitted_at <= submitted_at_after
    assert location.is_current is False
    assert location.status == "pending"
    assert location.location is not None


def test_create_location_raises_when_property_does_not_exist(db_session):
    service = PropertyLocationService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.create_location(
            property_id=uuid.uuid4(),
            submitted_by_id=uuid.uuid4(),
            latitude=-1.2921,
            longitude=36.8219,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
        )


def test_create_location_raises_when_property_already_has_location(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    submit_location(
        db_session,
        service,
        property,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
    )

    with pytest.raises(
        LocationSubmissionConflict,
        match="Property already has a pending location",
    ):
        submit_location(
            db_session,
            service,
            property,
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
        submit_location(
            db_session,
            service,
            property,
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
        submit_location(
            db_session,
            service,
            property,
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
        submit_location(
            db_session,
            service,
            property,
            latitude=-1.2921,
            longitude=36.8219,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
            accuracy_meters=-1,
        )


def test_get_location_does_not_return_pending_location(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    created_location = submit_location(
        db_session,
        service,
        property,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
        accuracy_meters=12.5,
    )

    assert created_location.status == "pending"
    with pytest.raises(
        ValueError,
        match="Current approved property location not found",
    ):
        service.get_location(property.id)


def test_get_location_requires_persisted_approval_evidence(db_session):
    property = create_test_property(db_session)
    location = submit_location(
        db_session,
        PropertyLocationService(db_session),
        property,
        **create_location_payload(),
    )

    # Simulate inconsistent persisted state: approval flags exist, but
    # the corresponding verification evidence is absent.
    location.status = "approved"
    location.is_current = True
    db_session.flush()

    with pytest.raises(
        ValueError,
        match="Current approved property location not found",
    ):
        PropertyLocationService(db_session).get_location(property.id)


def test_submission_after_legacy_location_creates_next_version(db_session):
    property = create_test_property(db_session)
    legacy_captured_at = datetime(2020, 1, 2, tzinfo=UTC)
    legacy = PropertyLocation(
        property_id=property.id,
        version_number=1,
        submitted_by_id=None,
        submitted_at=None,
        is_current=False,
        latitude=-1.25,
        longitude=36.75,
        location="SRID=4326;POINT(36.75 -1.25)",
        source="legacy_source",
        capture_method="legacy_capture",
        accuracy_meters=22.0,
        captured_at=legacy_captured_at,
        status="unverified",
    )
    db_session.add(legacy)
    db_session.flush()
    legacy_id = legacy.id
    legacy_property_id = legacy.property_id
    legacy_updated_at = legacy.updated_at
    legacy_created_at = legacy.created_at
    legacy_geometry = db_session.scalar(
        select(func.ST_AsEWKB(PropertyLocation.location)).where(
            PropertyLocation.id == legacy.id
        )
    )

    service = PropertyLocationService(db_session)
    submitted = submit_location(
        db_session,
        service,
        property,
        latitude=-1.2921,
        longitude=36.8219,
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
    )

    db_session.refresh(legacy)
    assert submitted.version_number == 2
    assert submitted.status == "pending"
    assert submitted.is_current is False
    assert legacy.id == legacy_id
    assert legacy.property_id == legacy_property_id
    assert legacy.version_number == 1
    assert legacy.latitude == -1.25
    assert legacy.longitude == 36.75
    assert legacy.source == "legacy_source"
    assert legacy.capture_method == "legacy_capture"
    assert legacy.accuracy_meters == 22.0
    assert legacy.captured_at == legacy_captured_at
    assert legacy.status == "unverified"
    assert legacy.is_current is False
    assert legacy.submitted_by_id is None
    assert legacy.submitted_at is None
    assert legacy.updated_at == legacy_updated_at
    assert legacy.created_at == legacy_created_at
    assert db_session.scalar(
        select(func.ST_AsEWKB(PropertyLocation.location)).where(
            PropertyLocation.id == legacy.id
        )
    ) == legacy_geometry


def test_pending_unique_violation_preserves_outer_transaction(
    db_session,
    monkeypatch,
):
    property = create_test_property(db_session)
    existing = submit_location(
        db_session,
        PropertyLocationService(db_session),
        property,
        **create_location_payload(),
    )
    db_session.commit()

    unrelated_user = User(
        email=f"unrelated-pending-transaction-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(unrelated_user)

    service = PropertyLocationService(db_session)
    monkeypatch.setattr(
        service.property_location_repository,
        "get_pending_by_property_id",
        lambda property_id: None,
    )

    with pytest.raises(
        LocationSubmissionConflict,
        match="Property already has a pending location",
    ):
        submit_location(
            db_session,
            service,
            property,
            **create_location_payload(),
        )

    assert db_session.is_active

    # The failed insert must not roll back unrelated caller work.
    persisted_user = db_session.scalar(
        select(User).where(User.email == unrelated_user.email)
    )
    assert persisted_user is not None

    locations = (
        db_session.query(PropertyLocation)
        .filter(PropertyLocation.property_id == property.id)
        .all()
    )
    assert len(locations) == 1
    assert locations[0].id == existing.id
    assert locations[0].version_number == 1
    assert locations[0].status == "pending"
    assert locations[0].is_current is False


def test_version_unique_violation_preserves_outer_transaction(
    db_session,
    monkeypatch,
):
    property = create_test_property(db_session)
    existing = PropertyLocation(
        property_id=property.id,
        version_number=1,
        latitude=-1.25,
        longitude=36.75,
        location="SRID=4326;POINT(36.75 -1.25)",
        source="legacy_source",
        capture_method="legacy_capture",
        captured_at=datetime.now(UTC),
        status="approved",
        is_current=False,
    )
    db_session.add(existing)
    db_session.commit()

    unrelated_user = User(
        email=f"unrelated-transaction-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(unrelated_user)

    service = PropertyLocationService(db_session)
    monkeypatch.setattr(
        service.property_location_repository,
        "get_max_version_number",
        lambda property_id: 0,
    )

    with pytest.raises(
        LocationSubmissionConflict,
        match="Property location version conflict; retry submission",
    ):
        submit_location(
            db_session,
            service,
            property,
            **create_location_payload(),
        )

    assert db_session.is_active

    # The failed location insert must not roll back unrelated caller work.
    persisted_user = db_session.scalar(
        select(User).where(User.email == unrelated_user.email)
    )
    assert persisted_user is not None

    locations = (
        db_session.query(PropertyLocation)
        .filter(PropertyLocation.property_id == property.id)
        .all()
    )
    assert len(locations) == 1
    assert locations[0].version_number == 1
    assert locations[0].status == "approved"


def test_employee_with_active_management_grant_can_submit_without_clearance(
    db_session,
):
    property = create_test_property(db_session)
    employee_user, _ = create_employee(db_session)
    db_session.add(
        PropertyAccess(
            user_id=employee_user.id,
            property_id=property.id,
            access_type=PropertyAction.PROPERTY_MANAGEMENT.value,
            is_active=True,
        )
    )
    db_session.flush()

    location = submit_as(
        PropertyLocationService(db_session),
        property,
        employee_user.id,
        **create_location_payload(),
    )

    assert location.submitted_by_id == employee_user.id
    assert location.status == "pending"


def test_employee_without_management_grant_cannot_submit(db_session):
    property = create_test_property(db_session)
    employee_user, _ = create_employee(db_session)

    with pytest.raises(ValueError, match="not authorized"):
        submit_as(
            PropertyLocationService(db_session),
            property,
            employee_user.id,
            **create_location_payload(),
        )


def test_employee_without_employee_record_cannot_submit(db_session):
    property = create_test_property(db_session)
    employee_user = User(
        email=f"location-no-record-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=True,
    )
    db_session.add(employee_user)
    db_session.flush()

    with pytest.raises(ValueError, match="Employee is terminated"):
        submit_as(
            PropertyLocationService(db_session),
            property,
            employee_user.id,
            **create_location_payload(),
        )

    locations = (
        db_session.query(PropertyLocation)
        .filter(PropertyLocation.property_id == property.id)
        .all()
    )
    assert locations == []


@pytest.mark.parametrize(
    ("active", "terminated", "message"),
    [
        (False, False, "inactive"),
        (True, True, "terminated"),
    ],
)
def test_inactive_or_terminated_employee_cannot_submit(
    db_session,
    active,
    terminated,
    message,
):
    property = create_test_property(db_session)
    employee_user, _ = create_employee(
        db_session,
        active=active,
        terminated=terminated,
    )
    db_session.add(
        PropertyAccess(
            user_id=employee_user.id,
            property_id=property.id,
            access_type=PropertyAction.PROPERTY_MANAGEMENT.value,
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(ValueError, match=message):
        submit_as(
            PropertyLocationService(db_session),
            property,
            employee_user.id,
            **create_location_payload(),
        )


def test_active_administrator_without_employee_or_grant_can_submit(db_session):
    property = create_test_property(db_session)
    administrator = User(
        email=f"location-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(administrator)
    db_session.flush()

    location = submit_as(
        PropertyLocationService(db_session),
        property,
        administrator.id,
        **create_location_payload(),
    )

    assert location.submitted_by_id == administrator.id
    assert location.status == "pending"


def test_inactive_administrator_cannot_submit(db_session):
    property = create_test_property(db_session)
    administrator = User(
        email=f"location-inactive-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=False,
    )
    db_session.add(administrator)
    db_session.flush()

    with pytest.raises(ValueError, match="inactive"):
        submit_as(
            PropertyLocationService(db_session),
            property,
            administrator.id,
            **create_location_payload(),
        )


def test_get_location_raises_when_location_does_not_exist(db_session):
    property = create_test_property(db_session)

    service = PropertyLocationService(db_session)

    with pytest.raises(
        ValueError,
        match="Current approved property location not found",
    ):
        service.get_location(property.id)


@pytest.mark.independent_db_transactions
def test_create_location_serializes_concurrent_creations_for_same_property(
    db_session,
):
    property = create_test_property(db_session)
    db_session.commit()
    landlord = db_session.get(Landlord, property.landlord_id)
    submitter_id = landlord.user_id

    first_session = SessionLocal()
    second_session = SessionLocal()
    first_service = PropertyLocationService(first_session)
    second_service = PropertyLocationService(second_session)
    first_service.property_repository.get_by_id_for_update(property.id)
    first_backend_pid = first_session.scalar(
        text("SELECT pg_backend_pid()")
    )
    second_pid_ready = Event()
    monitor_poll = Event()
    second_finished = Event()
    second_backend_pid = []
    second_error = []

    def create_second_location():
        try:
            backend_pid = second_session.scalar(
                text("SELECT pg_backend_pid()")
            )
            second_backend_pid.append(backend_pid)
            second_pid_ready.set()
            second_service.create_location(
                property_id=property.id,
                submitted_by_id=submitter_id,
                latitude=-1.3000,
                longitude=36.8300,
                source="landlord_provided",
                capture_method="manual_entry",
                captured_at=datetime.now(UTC),
            )
        except Exception as exc:
            second_error.append(exc)
        finally:
            try:
                second_session.rollback()
            except Exception as exc:
                second_error.append(exc)
            try:
                second_session.close()
            except Exception as exc:
                second_error.append(exc)
            second_finished.set()

    thread = Thread(target=create_second_location, daemon=True)
    monitor_connection = engine.connect()

    try:
        thread.start()
        assert second_pid_ready.wait(timeout=10)
        assert len(second_backend_pid) == 1
        assert second_backend_pid[0] != first_backend_pid

        deadline = monotonic() + 10
        blocking_state = None
        while monotonic() < deadline:
            blocking_state = monitor_connection.execute(
                text(
                    "SELECT wait_event_type, pg_blocking_pids(pid) "
                    "FROM pg_stat_activity WHERE pid = :pid"
                ),
                {"pid": second_backend_pid[0]},
            ).one_or_none()
            if (
                blocking_state is not None
                and blocking_state.wait_event_type == "Lock"
                and first_backend_pid
                in blocking_state.pg_blocking_pids
            ):
                break
            monitor_poll.wait(timeout=0.05)
        else:
            pytest.fail(
                "Second submission was not observed waiting on a lock "
                f"held by backend {first_backend_pid}; "
                f"last state was {blocking_state!r}"
            )

        first_service.create_location(
            property_id=property.id,
            submitted_by_id=submitter_id,
            latitude=-1.2921,
            longitude=36.8219,
            source="device_gps",
            capture_method="user_confirmed_device_location",
            captured_at=datetime.now(UTC),
        )
        first_session.commit()

        assert second_finished.wait(timeout=10)
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert len(second_error) == 1
        assert isinstance(second_error[0], LocationSubmissionConflict)
        assert str(second_error[0]) == (
            "Property already has a pending location"
        )

        locations = (
            db_session.query(PropertyLocation)
            .filter(PropertyLocation.property_id == property.id)
            .all()
        )
        pending_locations = [
            location
            for location in locations
            if location.status == "pending"
        ]

        assert len(locations) == 1
        assert len(pending_locations) == 1
        assert locations[0].version_number == 1
        assert locations[0].latitude == -1.2921
        assert locations[0].longitude == 36.8219
        assert locations[0].status == "pending"
    finally:
        try:
            first_session.rollback()
        finally:
            if thread.is_alive():
                thread.join(timeout=10)
            monitor_connection.close()
            first_session.close()


def test_property_location_rejects_invalid_status_at_database_level(db_session):
    property = create_test_property(db_session)

    location = PropertyLocation(
        property_id=property.id,
        latitude=-1.2921,
        longitude=36.8219,
        location="SRID=4326;POINT(36.8219 -1.2921)",
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
        status="invalid_status",
    )

    db_session.add(location)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("latitude", float("nan"), "Latitude must be between -90 and 90"),
        ("latitude", float("inf"), "Latitude must be between -90 and 90"),
        ("latitude", float("-inf"), "Latitude must be between -90 and 90"),
        ("longitude", float("nan"), "Longitude must be between -180 and 180"),
        ("longitude", float("inf"), "Longitude must be between -180 and 180"),
        ("longitude", float("-inf"), "Longitude must be between -180 and 180"),
        (
            "accuracy_meters",
            float("nan"),
            "Accuracy must be greater than or equal to 0",
        ),
        (
            "accuracy_meters",
            float("inf"),
            "Accuracy must be greater than or equal to 0",
        ),
        (
            "accuracy_meters",
            float("-inf"),
            "Accuracy must be greater than or equal to 0",
        ),
    ],
)
def test_create_location_rejects_non_finite_numeric_values(
    db_session,
    field,
    value,
    message,
):
    property = create_test_property(db_session)
    payload = create_location_payload()
    payload[field] = value

    with pytest.raises(ValueError, match=message):
        submit_location(
            db_session,
            PropertyLocationService(db_session),
            property,
            **payload,
        )


def test_create_location_rejects_naive_captured_at(db_session):
    property = create_test_property(db_session)
    payload = create_location_payload()
    payload["captured_at"] = datetime(2026, 11, 7, 12, 0, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        submit_location(
            db_session,
            PropertyLocationService(db_session),
            property,
            **payload,
        )


def test_current_verified_location_requires_approved_current_state_and_evidence(
    db_session,
):
    property = create_test_property(db_session)
    owner_id = db_session.get(Landlord, property.landlord_id).user_id
    now = datetime.now(UTC)

    locations = [
        PropertyLocation(
            property_id=property.id,
            version_number=1,
            submitted_by_id=owner_id,
            submitted_at=now,
            is_current=False,
            latitude=-1.25,
            longitude=36.75,
            location="SRID=4326;POINT(36.75 -1.25)",
            source="test_fixture",
            capture_method="manual_entry",
            captured_at=now,
            status="approved",
        ),
        PropertyLocation(
            property_id=property.id,
            version_number=2,
            submitted_by_id=owner_id,
            submitted_at=now,
            is_current=False,
            latitude=-1.26,
            longitude=36.76,
            location="SRID=4326;POINT(36.76 -1.26)",
            source="test_fixture",
            capture_method="manual_entry",
            captured_at=now,
            status="rejected",
        ),
        PropertyLocation(
            property_id=property.id,
            version_number=3,
            submitted_by_id=owner_id,
            submitted_at=now,
            is_current=True,
            latitude=-1.27,
            longitude=36.77,
            location="SRID=4326;POINT(36.77 -1.27)",
            source="test_fixture",
            capture_method="manual_entry",
            captured_at=now,
            status="approved",
        ),
    ]
    db_session.add_all(locations)
    db_session.flush()

    db_session.add_all(
        [
            PropertyLocationVerification(
                location_id=locations[0].id,
                verified_by=owner_id,
                decision="approved",
                verification_method="test_fixture",
                verified_at=now,
            ),
            PropertyLocationVerification(
                location_id=locations[1].id,
                verified_by=owner_id,
                decision="rejected",
                verification_method="test_fixture",
                verified_at=now,
            ),
            PropertyLocationVerification(
                location_id=locations[2].id,
                verified_by=owner_id,
                decision="approved",
                verification_method="test_fixture",
                verified_at=now,
            ),
        ]
    )
    db_session.flush()

    result = PropertyLocationRepository(
        db_session
    ).get_current_verified_location_by_property_id(property.id)

    assert result is not None
    assert result.id == locations[2].id
    assert result.status == "approved"
    assert result.is_current is True


def test_current_verified_location_rejects_location_without_verification(
    db_session,
):
    property = create_test_property(db_session)
    owner_id = db_session.get(Landlord, property.landlord_id).user_id
    now = datetime.now(UTC)

    location = PropertyLocation(
        property_id=property.id,
        version_number=1,
        submitted_by_id=owner_id,
        submitted_at=now,
        is_current=True,
        latitude=-1.27,
        longitude=36.77,
        location="SRID=4326;POINT(36.77 -1.27)",
        source="test_fixture",
        capture_method="manual_entry",
        captured_at=now,
        status="approved",
    )
    db_session.add(location)
    db_session.flush()

    result = PropertyLocationRepository(
        db_session
    ).get_current_verified_location_by_property_id(property.id)

    assert result is None
