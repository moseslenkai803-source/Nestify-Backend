import uuid

import pytest
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.property_actions import PropertyAction
from app.core.security import create_access_token
from app.main import app
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.property_location import PropertyLocation
from app.models.user import User
from app.services.property_location_verification_service import (
    PropertyLocationVerificationService,
)


def create_property_context(db_session):
    owner = User(
        email=f"location-api-owner-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )
    db_session.add(owner)
    db_session.flush()
    landlord = Landlord(
        user_id=owner.id,
        display_name="Location API Owner",
        phone=f"+2547{uuid.uuid4().int % 1000000000:09d}",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"LA-{uuid.uuid4().hex[:12].upper()}",
        name="Location API Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()
    return owner, property_record


def create_pending_location(db_session, property_record, submitter_id):
    location = PropertyLocation(
        property_id=property_record.id,
        version_number=1,
        submitted_by_id=submitter_id,
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
    db_session.add(location)
    db_session.flush()
    return location


def create_reviewer(db_session, property_id):
    reviewer = User(
        email=f"location-api-reviewer-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        is_active=True,
    )
    db_session.add(reviewer)
    db_session.flush()
    employee = Employee(
        user_id=reviewer.id,
        employee_number=f"LA-EMP-{uuid.uuid4().hex[:12]}",
        department="Operations",
        position="Location Reviewer",
    )
    db_session.add(employee)
    db_session.flush()
    db_session.add(
        EmployeeClearance(
            employee_id=employee.id,
            clearance="property_verification",
            is_active=True,
        )
    )
    db_session.add(
        PropertyAccess(
            user_id=reviewer.id,
            property_id=property_id,
            access_type=PropertyAction.PROPERTY_VERIFICATION.value,
            is_active=True,
        )
    )
    db_session.flush()
    return reviewer


def auth_header(user_id):
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def test_employee_can_approve_location_via_api(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        reviewer = create_reviewer(db_session, property_record.id)
        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/approve",
            headers=auth_header(reviewer.id),
            json={
                "verification_method": "independent_site_review",
                "notes": "Coordinates confirmed at site.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["location_id"] == str(location.id)
        assert data["verified_by"] == str(reviewer.id)
        assert data["decision"] == "approved"
        assert data["verification_method"] == "independent_site_review"
        assert data["verified_at"] is not None
        db_session.refresh(location)
        assert location.status == "approved"
        assert location.is_current is True
    finally:
        app.dependency_overrides.clear()


def test_active_admin_without_employee_can_reject_via_api(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        admin = User(
            email=f"location-api-admin-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()
        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/reject",
            headers=auth_header(admin.id),
            json={"verification_method": "document_review"},
        )

        assert response.status_code == 200
        assert response.json()["decision"] == "rejected"
        db_session.refresh(location)
        assert location.status == "rejected"
        assert location.is_current is False
    finally:
        app.dependency_overrides.clear()


def test_active_admin_without_employee_can_approve_via_api(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        admin = User(
            email=f"location-api-admin-approve-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()

        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/approve",
            headers=auth_header(admin.id),
            json={"verification_method": "document_review"},
        )

        assert response.status_code == 200
        assert response.json()["decision"] == "approved"
        assert response.json()["verified_by"] == str(admin.id)

        db_session.refresh(location)
        assert location.status == "approved"
        assert location.is_current is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_employee_without_employee_record_cannot_review_via_api(
    db_session,
    decision,
):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        reviewer = User(
            email=f"location-api-no-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()

        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/{decision}",
            headers=auth_header(reviewer.id),
            json={"verification_method": "document_review"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Active employee record is required"

        db_session.refresh(location)
        assert location.status == "pending"
        assert location.is_current is False
    finally:
        app.dependency_overrides.clear()


def test_self_review_is_forbidden_through_api(db_session):
    try:
        client = TestClient(app)
        _, property_record = create_property_context(db_session)
        reviewer = create_reviewer(db_session, property_record.id)
        location = create_pending_location(
            db_session,
            property_record,
            reviewer.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/approve",
            headers=auth_header(reviewer.id),
            json={"verification_method": "site_visit"},
        )

        assert response.status_code == 403
        assert "own location" in response.json()["detail"]
        assert location.status == "pending"
    finally:
        app.dependency_overrides.clear()


def test_history_and_review_queue_api_return_scoped_records(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        reviewer = create_reviewer(db_session, property_record.id)
        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )

        history_response = client.get(
            f"/api/v1/properties/{property_record.id}/locations/history",
            headers=auth_header(owner.id),
        )
        queue_response = client.get(
            "/api/v1/properties/locations/pending-verification",
            headers=auth_header(reviewer.id),
        )

        assert history_response.status_code == 200
        assert history_response.json()[0]["history_state"] == "pending"
        assert history_response.json()[0]["id"] == str(location.id)
        assert queue_response.status_code == 200
        assert [item["id"] for item in queue_response.json()] == [
            str(location.id)
        ]
    finally:
        app.dependency_overrides.clear()


def test_current_location_endpoint_returns_only_approved_current_location(
    db_session,
):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )
        pending_response = client.get(
            f"/api/v1/properties/{property_record.id}/location",
            headers=auth_header(owner.id),
        )
        assert pending_response.status_code == 404

        admin = User(
            email=f"location-api-current-admin-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()
        PropertyLocationVerificationService(db_session).approve_location(
            property_id=property_record.id,
            location_id=location.id,
            reviewer_id=admin.id,
            verification_method="independent_site_review",
        )

        current_response = client.get(
            f"/api/v1/properties/{property_record.id}/location",
            headers=auth_header(owner.id),
        )
        assert current_response.status_code == 200
        assert current_response.json()["status"] == "approved"
    finally:
        app.dependency_overrides.clear()


def test_history_is_forbidden_for_unrelated_user(db_session):
    try:
        client = TestClient(app)
        _, property_record = create_property_context(db_session)
        unrelated, _ = create_property_context(db_session)

        response = client.get(
            f"/api/v1/properties/{property_record.id}/locations/history",
            headers=auth_header(unrelated.id),
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_decision_endpoint_rejects_empty_verification_method(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        reviewer = create_reviewer(db_session, property_record.id)
        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/approve",
            headers=auth_header(reviewer.id),
            json={"verification_method": ""},
        )

        assert response.status_code == 422
        assert location.status == "pending"
    finally:
        app.dependency_overrides.clear()


def test_deciding_an_already_decided_location_returns_conflict(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        admin = User(
            email=f"location-api-repeat-admin-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()
        location = create_pending_location(
            db_session,
            property_record,
            owner.id,
        )
        headers = auth_header(admin.id)
        body = {"verification_method": "independent_site_review"}
        first_response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/approve",
            headers=headers,
            json=body,
        )
        second_response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/reject",
            headers=headers,
            json=body,
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 409
        db_session.refresh(location)
        assert location.status == "approved"
        assert location.is_current is True
    finally:
        app.dependency_overrides.clear()


def test_wrong_property_location_version_returns_not_found(db_session):
    try:
        client = TestClient(app)
        owner, property_record = create_property_context(db_session)
        _, other_property = create_property_context(db_session)
        admin = User(
            email=f"location-api-wrong-property-admin-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()
        location = create_pending_location(
            db_session,
            other_property,
            owner.id,
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/locations/"
            f"{location.id}/approve",
            headers=auth_header(admin.id),
            json={"verification_method": "independent_site_review"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Property location version not found"
        )
        assert location.status == "pending"
    finally:
        app.dependency_overrides.clear()
