import uuid
from datetime import UTC, datetime

import pytest

from app.core.property_actions import PropertyAction
from app.models.employee import Employee
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.user import User
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


def create_user(
    db_session,
    *,
    role="landlord",
    is_active=True,
    create_employee_record=True,
):
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()

    if role == "employee" and create_employee_record:
        db_session.add(
            Employee(
                user_id=user.id,
                employee_number=f"AUTH-{uuid.uuid4().hex[:20].upper()}",
                department="Operations",
                position="Test Employee",
            )
        )
        db_session.flush()

    return user


def create_landlord(db_session, user):
    landlord = Landlord(
        user_id=user.id,
        display_name="Test Landlord",
        phone="0700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()
    return landlord


def create_property(db_session, landlord):
    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Test Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()
    return property


def grant_property_access(
    db_session,
    user,
    property,
    action=PropertyAction.PLATE_OPERATIONS,
):
    access = PropertyAccess(
        user_id=user.id,
        property_id=property.id,
        access_type=action,
        is_active=True,
    )
    db_session.add(access)
    db_session.flush()
    return access


def test_property_owner_can_authorize_own_property(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property = create_property(db_session, landlord)

    service = PropertyAuthorizationService(db_session)

    authorized_property = service.authorize(
        user=user,
        property_id=property.id,
        action=PropertyAction.PROPERTY_MANAGEMENT,
    )

    assert authorized_property.id == property.id


def test_admin_can_authorize_any_existing_property(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)

    admin = create_user(
        db_session,
        role="admin",
    )

    service = PropertyAuthorizationService(db_session)

    authorized_property = service.authorize(
        user=admin,
        property_id=property.id,
        action=PropertyAction.INSTALLATION_VERIFICATION,
    )

    assert authorized_property.id == property.id


def test_landlord_cannot_authorize_another_landlords_property(db_session):
    owner = create_user(db_session)
    owner_landlord = create_landlord(db_session, owner)
    property = create_property(db_session, owner_landlord)

    other_user = create_user(db_session)
    create_landlord(db_session, other_user)

    service = PropertyAuthorizationService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.authorize(
            user=other_user,
            property_id=property.id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )


def test_user_with_active_property_access_can_authorize_property(
    db_session,
):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)

    employee = create_user(
        db_session,
        role="employee",
    )

    grant_property_access(
        db_session,
        employee,
        property,
        action=PropertyAction.PLATE_OPERATIONS,
    )

    service = PropertyAuthorizationService(db_session)

    authorized_property = service.authorize(
        user=employee,
        property_id=property.id,
        action=PropertyAction.PLATE_OPERATIONS,
    )

    assert authorized_property.id == property.id


def test_user_with_plate_request_access_can_authorize_plate_request(
    db_session,
):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)

    employee = create_user(
        db_session,
        role="employee",
    )

    grant_property_access(
        db_session,
        employee,
        property,
        action=PropertyAction.PLATE_REQUEST,
    )

    service = PropertyAuthorizationService(db_session)

    authorized_property = service.authorize(
        user=employee,
        property_id=property.id,
        action=PropertyAction.PLATE_REQUEST,
    )

    assert authorized_property.id == property.id


def test_user_without_property_access_cannot_authorize_property(
    db_session,
):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)

    employee = create_user(
        db_session,
        role="employee",
    )

    service = PropertyAuthorizationService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.authorize(
            user=employee,
            property_id=property.id,
            action=PropertyAction.PLATE_OPERATIONS,
        )


def test_revoked_property_access_cannot_authorize_property(
    db_session,
):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)

    employee = create_user(
        db_session,
        role="employee",
    )

    access = grant_property_access(
        db_session,
        employee,
        property,
        action=PropertyAction.PLATE_OPERATIONS,
    )
    access.is_active = False
    db_session.flush()

    service = PropertyAuthorizationService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.authorize(
            user=employee,
            property_id=property.id,
            action=PropertyAction.PLATE_OPERATIONS,
        )


def test_employee_without_employee_record_cannot_use_property_grant(
    db_session,
):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)
    employee = create_user(
        db_session,
        role="employee",
        create_employee_record=False,
    )
    grant_property_access(db_session, employee, property)
    service = PropertyAuthorizationService(db_session)

    with pytest.raises(ValueError, match="Employee record not found"):
        service.authorize(
            user=employee,
            property_id=property.id,
            action=PropertyAction.PLATE_OPERATIONS,
        )


def test_terminated_employee_cannot_use_property_grant_if_account_active(
    db_session,
):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property = create_property(db_session, landlord)
    employee = create_user(db_session, role="employee")
    employee_record = (
        db_session.query(Employee)
        .filter(Employee.user_id == employee.id)
        .one()
    )
    employee_record.ended_at = datetime.now(UTC)
    grant_property_access(db_session, employee, property)
    service = PropertyAuthorizationService(db_session)

    with pytest.raises(ValueError, match="Employee is terminated"):
        service.authorize(
            user=employee,
            property_id=property.id,
            action=PropertyAction.PLATE_OPERATIONS,
        )


def test_inactive_user_cannot_authorize_property(db_session):
    user = create_user(
        db_session,
        is_active=False,
    )

    service = PropertyAuthorizationService(db_session)

    with pytest.raises(
        ValueError,
        match="User account is inactive",
    ):
        service.authorize(
            user=user,
            property_id=uuid.uuid4(),
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )


def test_nonexistent_property_cannot_be_authorized(db_session):
    user = create_user(db_session)

    service = PropertyAuthorizationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property not found",
    ):
        service.authorize(
            user=user,
            property_id=uuid.uuid4(),
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )


def test_invalid_property_action_is_rejected(db_session):
    user = create_user(db_session)

    service = PropertyAuthorizationService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid property action",
    ):
        service.authorize(
            user=user,
            property_id=uuid.uuid4(),
            action="unsupported_action",
        )
