import uuid

import pytest

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.user import User
from app.services.property_access_service import PropertyAccessService


def create_user(db_session, role="employee"):
    user = User(
        email=f"property-access-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_property(db_session):
    landlord_user = create_user(
        db_session,
        role="landlord",
    )

    landlord = Landlord(
        user_id=landlord_user.id,
        display_name="Property Access Service Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Property Access Service Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    return property


def test_grant_access_creates_active_property_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    result = service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert result.id is not None
    assert result.user_id == employee.id
    assert result.property_id == property.id
    assert result.access_type == "plate_operations"
    assert result.is_active is True


def test_grant_access_rejects_blank_access_type(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Access type is required",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="   ",
        )


def test_grant_access_rejects_duplicate_active_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    with pytest.raises(
        ValueError,
        match="Employee already has this property access",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_authorize_returns_active_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    granted_access = service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    result = service.authorize(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert result.id == granted_access.id


def test_authorize_rejects_missing_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Employee does not have access to this property",
    ):
        service.authorize(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_authorize_rejects_missing_property(db_session):
    employee = create_user(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Property not found",
    ):
        service.authorize(
            user_id=employee.id,
            property_id=uuid.uuid4(),
            access_type="plate_operations",
        )


def test_authorize_rejects_inactive_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    access = PropertyAccess(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
        is_active=False,
    )
    db_session.add(access)
    db_session.flush()

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Employee does not have access to this property",
    ):
        service.authorize(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_list_user_access_returns_user_records(db_session):
    employee = create_user(db_session)
    property_one = create_property(db_session)
    property_two = create_property(db_session)

    service = PropertyAccessService(db_session)

    access_one = service.grant_access(
        user_id=employee.id,
        property_id=property_one.id,
        access_type="plate_operations",
    )

    access_two = service.grant_access(
        user_id=employee.id,
        property_id=property_two.id,
        access_type="property_verification",
    )

    result = service.list_user_access(employee.id)

    assert len(result) == 2
    assert {access.id for access in result} == {
        access_one.id,
        access_two.id,
    }


def test_revoke_access_deactivates_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    result = service.revoke_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert result.is_active is False


def test_revoke_access_rejects_missing_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Active property access not found",
    ):
        service.revoke_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )
