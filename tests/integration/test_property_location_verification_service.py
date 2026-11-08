import uuid
from datetime import UTC, datetime
from threading import Event, Thread
from time import monotonic

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.property_actions import PropertyAction
from app.db.session import SessionLocal, engine
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.property_location import PropertyLocation
from app.models.property_location_verification import (
    PropertyLocationVerification,
)
from app.models.user import User
from app.services.employee_service import EmployeeService
from app.services.property_access_service import PropertyAccessService
from app.services.property_location_verification_service import (
    LocationReviewAuthorizationError,
    LocationReviewConflict,
    LocationReviewNotFound,
    PropertyLocationVerificationService,
)


def create_property(db_session, suffix="property"):
    owner = User(
        email=f"location-review-owner-{suffix}-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(owner)
    db_session.flush()
    landlord = Landlord(
        user_id=owner.id,
        display_name="Location Review Owner",
        phone=f"+2547{uuid.uuid4().int % 1000000000:09d}",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"LR-{uuid.uuid4().hex[:12].upper()}",
        name="Location Review Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()
    return owner, property_record


def create_employee_reviewer(
    db_session,
    property_id,
    *,
    active=True,
    terminated=False,
    clearance=True,
    clearance_active=True,
    grant=True,
    grant_active=True,
):
    user = User(
        email=f"location-review-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=active,
    )
    db_session.add(user)
    db_session.flush()
    employee = Employee(
        user_id=user.id,
        employee_number=f"LR-EMP-{uuid.uuid4().hex[:12]}",
        department="Operations",
        position="Location Reviewer",
        ended_at=datetime.now(UTC) if terminated else None,
    )
    db_session.add(employee)
    db_session.flush()
    clearance_record = None
    if clearance:
        clearance_record = EmployeeClearance(
            employee_id=employee.id,
            clearance="property_verification",
            is_active=clearance_active,
        )
        db_session.add(clearance_record)
        db_session.flush()
    access_record = None
    if grant:
        access_record = PropertyAccess(
            user_id=user.id,
            property_id=property_id,
            access_type=PropertyAction.PROPERTY_VERIFICATION.value,
            is_active=grant_active,
        )
        db_session.add(access_record)
        db_session.flush()
    return user, employee, clearance_record, access_record


def create_pending_location(
    db_session,
    property_id,
    submitted_by_id,
    version=1,
):
    location = PropertyLocation(
        property_id=property_id,
        version_number=version,
        submitted_by_id=submitted_by_id,
        submitted_at=datetime.now(UTC),
        is_current=False,
        latitude=-1.2921 + version / 1000,
        longitude=36.8219,
        location=f"SRID=4326;POINT(36.8219 {-1.2921 + version / 1000})",
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
        status="pending",
    )
    db_session.add(location)
    db_session.flush()
    return location


def create_current_location(
    db_session,
    property_id,
    version=1,
):
    location = PropertyLocation(
        property_id=property_id,
        version_number=version,
        submitted_by_id=None,
        submitted_at=None,
        is_current=True,
        latitude=-1.25,
        longitude=36.75,
        location="SRID=4326;POINT(36.75 -1.25)",
        source="landlord_provided",
        capture_method="manual_entry",
        captured_at=datetime.now(UTC),
        status="approved",
    )
    db_session.add(location)
    db_session.flush()
    return location


def create_admin(db_session, active=True):
    admin = User(
        email=f"location-review-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=active,
    )
    db_session.add(admin)
    db_session.flush()
    return admin


def service_decide(
    service,
    property_record,
    location,
    reviewer_id,
    decision="approve",
):
    method = (
        service.approve_location
        if decision == "approve"
        else service.reject_location
    )
    return method(
        property_id=property_record.id,
        location_id=location.id,
        reviewer_id=reviewer_id,
        verification_method="independent_site_review",
        notes="Reviewed submitted location",
    )


def wait_until_blocked(
    monitor_connection,
    backend_pid,
    blocker_pid,
    timeout=10,
):
    deadline = monotonic() + timeout
    last_state = None
    while monotonic() < deadline:
        last_state = monitor_connection.execute(
            text(
                "SELECT wait_event_type, pg_blocking_pids(pid) "
                "FROM pg_stat_activity WHERE pid = :pid"
            ),
            {"pid": backend_pid},
        ).one_or_none()
        if (
            last_state is not None
            and last_state.wait_event_type == "Lock"
            and blocker_pid in last_state.pg_blocking_pids
        ):
            return
        Event().wait(0.05)
    pytest.fail(
        f"Backend {backend_pid} was not observed blocked by {blocker_pid}; "
        f"last state was {last_state!r}"
    )


def test_employee_reviewer_can_approve_location_and_records_audit_data(
    db_session,
):
    owner, property_record = create_property(db_session)
    reviewer, _, _, _ = create_employee_reviewer(
        db_session,
        property_record.id,
    )
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    before = datetime.now(UTC)

    verification = service_decide(
        PropertyLocationVerificationService(db_session),
        property_record,
        location,
        reviewer.id,
    )

    after = datetime.now(UTC)
    assert verification.location_id == location.id
    assert verification.verified_by == reviewer.id
    assert verification.decision == "approved"
    assert verification.verification_method == "independent_site_review"
    assert before <= verification.verified_at <= after
    assert verification.notes == "Reviewed submitted location"
    assert location.status == "approved"
    assert location.is_current is True


def test_active_administrator_without_employee_or_grant_can_approve(
    db_session,
):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )

    decision = service_decide(
        PropertyLocationVerificationService(db_session),
        property_record,
        location,
        admin.id,
    )

    assert decision.verified_by == admin.id
    assert location.status == "approved"
    assert location.is_current is True


def test_inactive_administrator_cannot_review(db_session):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session, active=False)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )

    with pytest.raises(LocationReviewAuthorizationError):
        service_decide(
            PropertyLocationVerificationService(db_session),
            property_record,
            location,
            admin.id,
        )

    assert location.status == "pending"


@pytest.mark.parametrize(
    (
        "active",
        "employee_record",
        "terminated",
        "clearance",
        "clearance_active",
        "grant",
        "grant_active",
    ),
    [
        (True, False, False, True, True, True, True),
        (True, True, True, True, True, True, True),
        (True, True, False, False, False, True, True),
        (True, True, False, True, False, True, True),
        (True, True, False, True, True, False, False),
        (True, True, False, True, True, True, False),
        (False, True, False, True, True, True, True),
    ],
)
def test_employee_without_valid_reviewer_authorization_is_denied(
    db_session,
    active,
    employee_record,
    terminated,
    clearance,
    clearance_active,
    grant,
    grant_active,
):
    owner, property_record = create_property(db_session)
    if employee_record:
        reviewer, _, _, _ = create_employee_reviewer(
            db_session,
            property_record.id,
            active=active,
            terminated=terminated,
            clearance=clearance,
            clearance_active=clearance_active,
            grant=grant,
            grant_active=grant_active,
        )
    else:
        reviewer = User(
            email=f"location-review-no-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            is_active=active,
        )
        db_session.add(reviewer)
        db_session.flush()
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )

    with pytest.raises(LocationReviewAuthorizationError):
        service_decide(
            PropertyLocationVerificationService(db_session),
            property_record,
            location,
            reviewer.id,
        )

    assert location.status == "pending"


@pytest.mark.parametrize("admin_reviewer", [False, True])
def test_submitter_cannot_review_own_location(db_session, admin_reviewer):
    _, property_record = create_property(db_session)
    if admin_reviewer:
        reviewer = create_admin(db_session)
    else:
        reviewer, _, _, _ = create_employee_reviewer(
            db_session,
            property_record.id,
        )
    location = create_pending_location(
        db_session,
        property_record.id,
        reviewer.id,
    )

    with pytest.raises(
        LocationReviewAuthorizationError,
        match="own location",
    ):
        service_decide(
            PropertyLocationVerificationService(db_session),
            property_record,
            location,
            reviewer.id,
        )

    assert location.status == "pending"


def test_current_location_requires_persisted_approval_evidence(db_session):
    _, property_record = create_property(db_session)
    admin = create_admin(db_session)
    create_current_location(db_session, property_record.id)

    service = PropertyLocationVerificationService(db_session)

    with pytest.raises(
        LocationReviewNotFound,
        match="Current approved property location not found",
    ):
        service.get_current_location(property_record.id, admin.id)


def test_approval_replaces_current_location_without_deleting_history(
    db_session,
):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    previous = create_current_location(db_session, property_record.id)
    submitted = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
        version=2,
    )

    service_decide(
        PropertyLocationVerificationService(db_session),
        property_record,
        submitted,
        reviewer.id,
    )

    assert previous in db_session.query(PropertyLocation).filter_by(
        property_id=property_record.id
    ).all()
    assert previous.status == "approved"
    assert previous.is_current is False
    assert submitted.status == "approved"
    assert submitted.is_current is True
    assert (
        db_session.query(PropertyLocation)
        .filter_by(property_id=property_record.id, is_current=True)
        .count()
        == 1
    )


def test_rejection_preserves_current_and_rejected_version_cannot_be_approved(
    db_session,
):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    current = create_current_location(db_session, property_record.id)
    submitted = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
        version=2,
    )
    service = PropertyLocationVerificationService(db_session)

    decision = service_decide(
        service,
        property_record,
        submitted,
        reviewer.id,
        decision="reject",
    )

    assert decision.decision == "rejected"
    assert submitted.status == "rejected"
    assert submitted.is_current is False
    assert current.status == "approved"
    assert current.is_current is True
    with pytest.raises(LocationReviewConflict):
        service_decide(
            service,
            property_record,
            submitted,
            reviewer.id,
        )


def test_already_decided_location_cannot_be_decided_again(db_session):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    service = PropertyLocationVerificationService(db_session)
    service_decide(service, property_record, location, reviewer.id)

    with pytest.raises(LocationReviewConflict):
        service_decide(
            service,
            property_record,
            location,
            reviewer.id,
            decision="reject",
        )


def test_wrong_property_location_version_is_not_found(db_session):
    owner, property_record = create_property(db_session, "first")
    _, other_property = create_property(db_session, "second")
    reviewer = create_admin(db_session)
    location = create_pending_location(
        db_session,
        other_property.id,
        owner.id,
    )

    with pytest.raises(LocationReviewNotFound):
        service_decide(
            PropertyLocationVerificationService(db_session),
            property_record,
            location,
            reviewer.id,
        )


def test_failed_approval_preserves_outer_transaction_and_current_location(
    db_session,
    monkeypatch,
):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    current = create_current_location(db_session, property_record.id)
    submitted = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
        version=2,
    )
    db_session.commit()
    current_id = current.id
    submitted_id = submitted.id

    unrelated_email = f"unrelated-{uuid.uuid4()}@example.com"
    unrelated_user = User(
        email=unrelated_email,
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(unrelated_user)

    service = PropertyLocationVerificationService(db_session)

    def fail_after_flush(verification):
        db_session.add(verification)
        db_session.flush()
        raise RuntimeError("forced failure after decision flush")

    monkeypatch.setattr(service.verification_repository, "add", fail_after_flush)
    with pytest.raises(RuntimeError, match="forced failure"):
        service_decide(service, property_record, submitted, reviewer.id)

    assert db_session.is_active
    assert (
        db_session.query(User)
        .filter_by(email=unrelated_email)
        .one_or_none()
        is not None
    )

    current = db_session.get(PropertyLocation, current_id)
    submitted = db_session.get(PropertyLocation, submitted_id)
    assert current.status == "approved"
    assert current.is_current is True
    assert submitted.status == "pending"
    assert submitted.is_current is False
    assert (
        db_session.query(PropertyLocationVerification)
        .filter_by(location_id=submitted_id)
        .count()
        == 0
    )


def test_location_history_is_authorized_and_ordered_with_state_labels(
    db_session,
):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session)
    legacy = PropertyLocation(
        property_id=property_record.id,
        version_number=1,
        submitted_by_id=None,
        submitted_at=None,
        is_current=False,
        latitude=-1.25,
        longitude=36.75,
        location="SRID=4326;POINT(36.75 -1.25)",
        source="legacy",
        capture_method="legacy",
        captured_at=datetime(2020, 1, 1, tzinfo=UTC),
        status="unverified",
    )
    db_session.add(legacy)
    db_session.flush()
    pending = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
        version=2,
    )
    current = create_current_location(
        db_session,
        property_record.id,
        version=3,
    )
    db_session.add(
        PropertyLocationVerification(
            location_id=current.id,
            verified_by=admin.id,
            decision="approved",
            verification_method="site_visit",
            verified_at=datetime.now(UTC),
            notes="Verified",
        )
    )
    db_session.flush()

    history = PropertyLocationVerificationService(db_session).get_location_history(
        property_record.id,
        owner.id,
    )

    assert [item["version_number"] for item in history] == [3, 2, 1]
    assert [item["history_state"] for item in history] == [
        "current",
        "pending",
        "legacy",
    ]
    assert history[1]["id"] == pending.id
    assert history[0]["verification"].decision == "approved"


def test_admin_can_view_location_history(db_session):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )

    history = PropertyLocationVerificationService(
        db_session
    ).get_location_history(property_record.id, admin.id)

    assert [
        (item["property_id"], item["id"])
        for item in history
    ] == [(property_record.id, location.id)]


def test_history_distinguishes_superseded_and_rejected_versions(db_session):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session)
    old_approved = PropertyLocation(
        property_id=property_record.id,
        version_number=1,
        submitted_by_id=owner.id,
        submitted_at=datetime.now(UTC),
        is_current=False,
        latitude=-1.25,
        longitude=36.75,
        location="SRID=4326;POINT(36.75 -1.25)",
        source="landlord_provided",
        capture_method="manual_entry",
        captured_at=datetime.now(UTC),
        status="approved",
    )
    rejected = PropertyLocation(
        property_id=property_record.id,
        version_number=2,
        submitted_by_id=owner.id,
        submitted_at=datetime.now(UTC),
        is_current=False,
        latitude=-1.26,
        longitude=36.76,
        location="SRID=4326;POINT(36.76 -1.26)",
        source="landlord_provided",
        capture_method="manual_entry",
        captured_at=datetime.now(UTC),
        status="rejected",
    )
    current = create_current_location(
        db_session,
        property_record.id,
        version=3,
    )
    db_session.add_all([old_approved, rejected])
    db_session.flush()
    db_session.add_all(
        [
            PropertyLocationVerification(
                location_id=old_approved.id,
                verified_by=admin.id,
                decision="approved",
                verification_method="site_visit",
                verified_at=datetime.now(UTC),
            ),
            PropertyLocationVerification(
                location_id=rejected.id,
                verified_by=admin.id,
                decision="rejected",
                verification_method="site_visit",
                verified_at=datetime.now(UTC),
            ),
            PropertyLocationVerification(
                location_id=current.id,
                verified_by=admin.id,
                decision="approved",
                verification_method="site_visit",
                verified_at=datetime.now(UTC),
            ),
        ]
    )
    db_session.flush()

    history = PropertyLocationVerificationService(db_session).get_location_history(
        property_record.id,
        owner.id,
    )

    assert [item["history_state"] for item in history] == [
        "current",
        "rejected",
        "superseded",
    ]


def test_property_manager_and_authorized_reviewer_can_view_history(
    db_session,
):
    owner, property_record = create_property(db_session)
    manager, _, _, _ = create_employee_reviewer(
        db_session,
        property_record.id,
        clearance=False,
    )
    management_grant = PropertyAccess(
        user_id=manager.id,
        property_id=property_record.id,
        access_type=PropertyAction.PROPERTY_MANAGEMENT.value,
        is_active=True,
    )
    db_session.add(management_grant)
    reviewer, _, _, _ = create_employee_reviewer(
        db_session,
        property_record.id,
    )
    create_pending_location(db_session, property_record.id, owner.id)
    service = PropertyLocationVerificationService(db_session)

    assert len(service.get_location_history(property_record.id, manager.id)) == 1
    assert len(service.get_location_history(property_record.id, reviewer.id)) == 1


def test_unauthorized_user_cannot_view_history(db_session):
    owner, property_record = create_property(db_session)
    unrelated, _ = create_property(db_session, "unrelated")
    create_pending_location(db_session, property_record.id, owner.id)
    service = PropertyLocationVerificationService(db_session)

    with pytest.raises(LocationReviewAuthorizationError):
        service.get_location_history(property_record.id, unrelated.id)


def test_employee_queue_is_scoped_and_admin_queue_is_global(db_session):
    preexisting_pending_ids = {
        row[0]
        for row in db_session.query(PropertyLocation.id)
        .filter(PropertyLocation.status == "pending")
        .all()
    }
    owner_a, property_a = create_property(db_session, "queue-a")
    owner_b, property_b = create_property(db_session, "queue-b")
    reviewer, _, _, _ = create_employee_reviewer(
        db_session,
        property_a.id,
    )
    create_pending_location(db_session, property_a.id, owner_a.id)
    create_pending_location(db_session, property_b.id, owner_b.id)
    service = PropertyLocationVerificationService(db_session)

    employee_queue = service.list_pending_reviews(reviewer.id)
    assert [item["property_id"] for item in employee_queue] == [
        property_a.id
    ]

    admin = create_admin(db_session)
    admin_queue = service.list_pending_reviews(admin.id)
    admin_queue_ids = {item["id"] for item in admin_queue}
    expected_ids = {
        item["id"]
        for item in employee_queue
    } | {
        item.id
        for item in service.location_repository.get_pending_by_property_ids(
            [property_b.id]
        )
    }
    assert expected_ids <= admin_queue_ids
    assert admin_queue_ids - preexisting_pending_ids == expected_ids


def test_employee_queue_excludes_property_after_verification_grant_revoked(
    db_session,
):
    owner_a, property_a = create_property(db_session, "revoked-queue-a")
    owner_b, property_b = create_property(db_session, "revoked-queue-b")
    reviewer, _, _, _ = create_employee_reviewer(
        db_session,
        property_a.id,
    )
    second_grant = PropertyAccess(
        user_id=reviewer.id,
        property_id=property_b.id,
        access_type=PropertyAction.PROPERTY_VERIFICATION.value,
        is_active=True,
    )
    db_session.add(second_grant)
    db_session.flush()
    location_a = create_pending_location(
        db_session,
        property_a.id,
        owner_a.id,
    )
    location_b = create_pending_location(
        db_session,
        property_b.id,
        owner_b.id,
    )
    PropertyAccessService(db_session).revoke_access(
        user_id=reviewer.id,
        property_id=property_b.id,
        access_type=PropertyAction.PROPERTY_VERIFICATION.value,
    )

    queue = PropertyLocationVerificationService(
        db_session
    ).list_pending_reviews(reviewer.id)

    assert [item["id"] for item in queue] == [location_a.id]
    assert [item["property_id"] for item in queue] == [property_a.id]
    assert location_b.id not in {item["id"] for item in queue}


def test_employee_without_active_clearance_cannot_read_review_queue(
    db_session,
):
    owner, property_record = create_property(db_session)
    reviewer, employee, clearance, _ = create_employee_reviewer(
        db_session,
        property_record.id,
    )
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    EmployeeService(db_session).remove_clearance(
        employee_id=employee.id,
        clearance="property_verification",
    )

    with pytest.raises(LocationReviewAuthorizationError):
        PropertyLocationVerificationService(
            db_session
        ).list_pending_reviews(reviewer.id)

    db_session.refresh(clearance)
    assert clearance.is_active is False
    assert location.status == "pending"


@pytest.mark.parametrize(
    ("active", "terminated"),
    [(False, False), (True, True)],
    ids=["inactive-user", "terminated-employee"],
)
def test_inactive_or_terminated_employee_cannot_read_review_queue(
    db_session,
    active,
    terminated,
):
    owner, property_record = create_property(db_session)
    reviewer, _, _, _ = create_employee_reviewer(
        db_session,
        property_record.id,
        active=active,
        terminated=terminated,
    )
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )

    with pytest.raises(LocationReviewAuthorizationError):
        PropertyLocationVerificationService(
            db_session
        ).list_pending_reviews(reviewer.id)

    assert location.status == "pending"



def test_duplicate_decision_constraint_preserves_outer_transaction(
    db_session,
    monkeypatch,
):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )

    db_session.add(
        PropertyLocationVerification(
            location_id=location.id,
            verified_by=reviewer.id,
            decision="rejected",
            verification_method="independent_site_review",
            verified_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    location_id = location.id
    unrelated_email = f"unrelated-{uuid.uuid4()}@example.com"
    db_session.add(
        User(
            email=unrelated_email,
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
    )

    service = PropertyLocationVerificationService(db_session)

    # Simulate a stale read so the database unique constraint detects
    # the duplicate decision during the verification insert.
    monkeypatch.setattr(
        service.verification_repository,
        "get_by_location_id",
        lambda location_id: None,
    )

    with pytest.raises(LocationReviewConflict):
        service_decide(
            service,
            property_record,
            location,
            reviewer.id,
            decision="reject",
        )

    assert db_session.is_active
    assert (
        db_session.query(User)
        .filter_by(email=unrelated_email)
        .one_or_none()
        is not None
    )

    persisted_location = db_session.get(PropertyLocation, location_id)
    assert persisted_location.status == "pending"
    assert persisted_location.is_current is False

    verifications = (
        db_session.query(PropertyLocationVerification)
        .filter_by(location_id=location_id)
        .all()
    )
    assert len(verifications) == 1
    assert verifications[0].decision == "rejected"


def test_current_location_constraint_preserves_outer_transaction(
    db_session,
    monkeypatch,
):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    current = create_current_location(db_session, property_record.id)
    submitted = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
        version=2,
    )
    db_session.commit()

    current_id = current.id
    submitted_id = submitted.id
    unrelated_email = f"unrelated-{uuid.uuid4()}@example.com"

    db_session.add(
        User(
            email=unrelated_email,
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
    )

    service = PropertyLocationVerificationService(db_session)

    # Simulate a stale read so PostgreSQL enforces the one-current index.
    monkeypatch.setattr(
        service.location_repository,
        "get_current_by_property_id_for_update",
        lambda property_id: None,
    )

    with pytest.raises(LocationReviewConflict):
        service_decide(
            service,
            property_record,
            submitted,
            reviewer.id,
        )

    assert db_session.is_active
    assert (
        db_session.query(User)
        .filter_by(email=unrelated_email)
        .one_or_none()
        is not None
    )

    persisted_current = db_session.get(PropertyLocation, current_id)
    persisted_submitted = db_session.get(PropertyLocation, submitted_id)

    assert persisted_current.status == "approved"
    assert persisted_current.is_current is True
    assert persisted_submitted.status == "pending"
    assert persisted_submitted.is_current is False

    assert (
        db_session.query(PropertyLocationVerification)
        .filter_by(location_id=submitted_id)
        .count()
        == 0
    )


def test_verification_decision_constraint_rejects_duplicate_location_decision(
    db_session,
):
    owner, property_record = create_property(db_session)
    reviewer = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    first = PropertyLocationVerification(
        location_id=location.id,
        verified_by=reviewer.id,
        decision="approved",
        verification_method="site_visit",
        verified_at=datetime.now(UTC),
    )
    db_session.add(first)
    db_session.flush()
    duplicate = PropertyLocationVerification(
        location_id=location.id,
        verified_by=reviewer.id,
        decision="rejected",
        verification_method="site_visit",
        verified_at=datetime.now(UTC),
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_verification_decision_constraint_rejects_invalid_decision(
    db_session,
):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    db_session.add(
        PropertyLocationVerification(
            location_id=location.id,
            verified_by=admin.id,
            decision="pending",
            verification_method="site_visit",
            verified_at=datetime.now(UTC),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.parametrize("second_decision", ["approve", "reject"])
@pytest.mark.independent_db_transactions
def test_concurrent_reviewers_cannot_decide_one_version_twice(
    db_session,
    second_decision,
):
    owner, property_record = create_property(db_session)
    first_reviewer = create_admin(db_session)
    second_reviewer = create_admin(db_session)
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    db_session.commit()

    first_session = SessionLocal()
    first_service = PropertyLocationVerificationService(first_session)
    first_service.property_repository.get_by_id_for_update(
        property_record.id
    )
    first_backend_pid = first_session.scalar(
        text("SELECT pg_backend_pid()")
    )
    second_backend_pid = []
    second_started = Event()
    second_finished = Event()
    second_result = []

    def decide_in_second_transaction():
        second_session = SessionLocal()
        try:
            second_backend_pid.append(
                second_session.scalar(text("SELECT pg_backend_pid()"))
            )
            second_started.set()
            second_service = PropertyLocationVerificationService(
                second_session
            )
            service_decide(
                second_service,
                property_record,
                location,
                second_reviewer.id,
                decision=second_decision,
            )
            second_result.append(None)
        except Exception as exc:
            second_result.append(exc)
        finally:
            second_session.rollback()
            second_session.close()
            second_finished.set()

    thread = Thread(target=decide_in_second_transaction, daemon=True)
    monitor_connection = engine.connect()
    try:
        thread.start()
        assert second_started.wait(timeout=10)
        assert second_backend_pid[0] != first_backend_pid
        wait_until_blocked(
            monitor_connection,
            second_backend_pid[0],
            first_backend_pid,
        )

        service_decide(
            first_service,
            property_record,
            location,
            first_reviewer.id,
            decision="approve",
        )
        first_session.commit()

        assert second_finished.wait(timeout=10)
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert len(second_result) == 1
        assert isinstance(second_result[0], LocationReviewConflict)

        decisions = (
            db_session.query(PropertyLocationVerification)
            .filter_by(location_id=location.id)
            .all()
        )
        assert len(decisions) == 1
        assert decisions[0].verified_by == first_reviewer.id
        assert decisions[0].decision == "approved"
        db_session.refresh(location)
        assert location.status == "approved"
        assert location.is_current is True
    finally:
        first_session.rollback()
        if thread.is_alive():
            thread.join(timeout=10)
        monitor_connection.close()
        first_session.close()


@pytest.mark.independent_db_transactions
def test_concurrent_rejection_prevents_waiting_approval(db_session):
    owner, property_record = create_property(db_session)
    current = create_current_location(
        db_session,
        property_record.id,
        version=1,
    )
    pending = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
        version=2,
    )
    rejecting_reviewer = create_admin(db_session)
    approving_reviewer = create_admin(db_session)
    db_session.commit()

    first_session = SessionLocal()
    first_service = PropertyLocationVerificationService(first_session)
    first_service.property_repository.get_by_id_for_update(
        property_record.id
    )
    first_backend_pid = first_session.scalar(
        text("SELECT pg_backend_pid()")
    )
    second_backend_pid = []
    second_started = Event()
    second_finished = Event()
    second_result = []

    def approve_in_second_transaction():
        second_session = SessionLocal()
        try:
            second_backend_pid.append(
                second_session.scalar(text("SELECT pg_backend_pid()"))
            )
            second_started.set()
            PropertyLocationVerificationService(
                second_session
            ).approve_location(
                property_id=property_record.id,
                location_id=pending.id,
                reviewer_id=approving_reviewer.id,
                verification_method="independent_site_review",
            )
            second_result.append(None)
        except Exception as exc:
            second_result.append(exc)
        finally:
            second_session.rollback()
            second_session.close()
            second_finished.set()

    thread = Thread(
        target=approve_in_second_transaction,
        daemon=True,
    )
    monitor_connection = engine.connect()
    try:
        thread.start()
        assert second_started.wait(timeout=10)
        assert second_backend_pid[0] != first_backend_pid
        wait_until_blocked(
            monitor_connection,
            second_backend_pid[0],
            first_backend_pid,
        )

        first_service.reject_location(
            property_id=property_record.id,
            location_id=pending.id,
            reviewer_id=rejecting_reviewer.id,
            verification_method="independent_site_review",
        )
        first_session.commit()

        assert second_finished.wait(timeout=10)
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert len(second_result) == 1
        assert isinstance(second_result[0], LocationReviewConflict)

        db_session.refresh(pending)
        db_session.refresh(current)
        assert pending.status == "rejected"
        assert pending.is_current is False
        assert current.status == "approved"
        assert current.is_current is True

        decisions = (
            db_session.query(PropertyLocationVerification)
            .filter_by(location_id=pending.id)
            .all()
        )
        assert len(decisions) == 1
        assert decisions[0].verified_by == rejecting_reviewer.id
        assert decisions[0].decision == "rejected"
        assert (
            db_session.query(PropertyLocation)
            .filter_by(property_id=property_record.id, is_current=True)
            .count()
            == 1
        )
    finally:
        first_session.rollback()
        if thread.is_alive():
            thread.join(timeout=10)
        monitor_connection.close()
        first_session.close()


@pytest.mark.independent_db_transactions
def test_concurrent_submission_and_review_are_serialized(db_session):
    owner, property_record = create_property(db_session)
    admin = create_admin(db_session)
    db_session.commit()

    submission_session = SessionLocal()
    submission_service = PropertyLocationVerificationService(
        submission_session
    )
    submission_service.property_repository.get_by_id_for_update(
        property_record.id
    )
    reviewer_backend_pid = []
    reviewer_started = Event()
    reviewer_finished = Event()
    reviewer_result = []
    submission = PropertyLocation(
        property_id=property_record.id,
        version_number=1,
        submitted_by_id=owner.id,
        submitted_at=datetime.now(UTC),
        is_current=False,
        latitude=-1.2921,
        longitude=36.8219,
        location="SRID=4326;POINT(36.8219 -1.2921)",
        source="device_gps",
        capture_method="user_confirmed_device_location",
        captured_at=datetime.now(UTC),
        status="pending",
    )
    submission_session.add(submission)
    submission_session.flush()
    submission_session_pid = submission_session.scalar(
        text("SELECT pg_backend_pid()")
    )

    def review_in_second_transaction():
        second_session = SessionLocal()
        try:
            reviewer_backend_pid.append(
                second_session.scalar(text("SELECT pg_backend_pid()"))
            )
            reviewer_started.set()
            decision = PropertyLocationVerificationService(
                second_session
            ).approve_location(
                property_id=property_record.id,
                location_id=submission.id,
                reviewer_id=admin.id,
                verification_method="independent_site_review",
            )
            reviewer_result.append(decision)
            second_session.commit()
        except Exception as exc:
            reviewer_result.append(exc)
            second_session.rollback()
        finally:
            second_session.close()
            reviewer_finished.set()

    thread = Thread(target=review_in_second_transaction, daemon=True)
    monitor_connection = engine.connect()
    try:
        thread.start()
        assert reviewer_started.wait(timeout=10)
        assert reviewer_backend_pid[0] != submission_session_pid
        wait_until_blocked(
            monitor_connection,
            reviewer_backend_pid[0],
            submission_session_pid,
        )

        submission_session.commit()
        assert reviewer_finished.wait(timeout=10)
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert len(reviewer_result) == 1
        assert isinstance(reviewer_result[0], PropertyLocationVerification)

        persisted_submission = db_session.get(
            PropertyLocation,
            submission.id,
        )
        assert persisted_submission.status == "approved"
        assert persisted_submission.is_current is True
        assert (
            db_session.query(PropertyLocationVerification)
            .filter_by(location_id=submission.id)
            .count()
            == 1
        )
    finally:
        submission_session.rollback()
        if thread.is_alive():
            thread.join(timeout=10)
        monitor_connection.close()
        submission_session.close()


@pytest.mark.parametrize("revocation", ["property_access", "clearance", "termination"])
@pytest.mark.independent_db_transactions
def test_revocation_serializes_with_location_review(
    db_session,
    revocation,
):
    owner, property_record = create_property(db_session)
    reviewer, employee, clearance, access = create_employee_reviewer(
        db_session,
        property_record.id,
    )
    location = create_pending_location(
        db_session,
        property_record.id,
        owner.id,
    )
    db_session.commit()

    revocation_session = SessionLocal()
    reviewer_backend_pid = []
    reviewer_started = Event()
    reviewer_finished = Event()
    reviewer_result = []

    if revocation == "property_access":
        PropertyAccessService(revocation_session).revoke_access(
            user_id=reviewer.id,
            property_id=property_record.id,
            access_type=PropertyAction.PROPERTY_VERIFICATION.value,
        )
    elif revocation == "clearance":
        EmployeeService(revocation_session).remove_clearance(
            employee_id=employee.id,
            clearance="property_verification",
        )
    else:
        EmployeeService(revocation_session).terminate_employee(
            employee_id=employee.id,
        )

    revocation_backend_pid = revocation_session.scalar(
        text("SELECT pg_backend_pid()")
    )

    def review_during_revocation():
        second_session = SessionLocal()
        try:
            reviewer_backend_pid.append(
                second_session.scalar(text("SELECT pg_backend_pid()"))
            )
            reviewer_started.set()
            PropertyLocationVerificationService(second_session).approve_location(
                property_id=property_record.id,
                location_id=location.id,
                reviewer_id=reviewer.id,
                verification_method="independent_site_review",
            )
            reviewer_result.append(None)
        except Exception as exc:
            reviewer_result.append(exc)
        finally:
            second_session.rollback()
            second_session.close()
            reviewer_finished.set()

    thread = Thread(target=review_during_revocation, daemon=True)
    monitor_connection = engine.connect()
    try:
        thread.start()
        assert reviewer_started.wait(timeout=10)
        assert reviewer_backend_pid[0] != revocation_backend_pid
        wait_until_blocked(
            monitor_connection,
            reviewer_backend_pid[0],
            revocation_backend_pid,
        )

        revocation_session.commit()
        assert reviewer_finished.wait(timeout=10)
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert len(reviewer_result) == 1
        assert isinstance(
            reviewer_result[0],
            LocationReviewAuthorizationError,
        )

        db_session.refresh(location)
        assert location.status == "pending"
        assert (
            db_session.query(PropertyLocationVerification)
            .filter_by(location_id=location.id)
            .count()
            == 0
        )
        if revocation == "property_access":
            db_session.refresh(access)
            assert access.is_active is False
        elif revocation == "clearance":
            db_session.refresh(clearance)
            assert clearance.is_active is False
        else:
            db_session.refresh(employee)
            assert employee.ended_at is not None
    finally:
        revocation_session.rollback()
        if thread.is_alive():
            thread.join(timeout=10)
        monitor_connection.close()
        revocation_session.close()
