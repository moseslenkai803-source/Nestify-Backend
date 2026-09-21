import uuid

from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.user import User
from app.repositories.property_access_repository import (
    PropertyAccessRepository,
)


def create_user(db_session, role="employee"):
    user = User(
        email=f"property-access-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_property(db_session):
    user = create_user(db_session, role="landlord")

    from app.models.landlord import Landlord

    landlord = Landlord(
        user_id=user.id,
        display_name="Property Access Test Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Property Access Test Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property)
    db_session.flush()

    return property


def test_add_property_access(db_session):
    user = create_user(db_session)
    property = create_property(db_session)

    repository = PropertyAccessRepository(db_session)

    access = PropertyAccess(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
        is_active=True,
    )

    result = repository.add(access)

    assert result.id is not None
    assert result.user_id == user.id
    assert result.property_id == property.id
    assert result.access_type == "plate_operations"
    assert result.is_active is True


def test_get_active_access_returns_matching_access(db_session):
    user = create_user(db_session)
    property = create_property(db_session)

    access = PropertyAccess(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
        is_active=True,
    )
    db_session.add(access)
    db_session.flush()

    repository = PropertyAccessRepository(db_session)

    result = repository.get_active_access(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert result is not None
    assert result.id == access.id


def test_get_active_access_ignores_inactive_access(db_session):
    user = create_user(db_session)
    property = create_property(db_session)

    access = PropertyAccess(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
        is_active=False,
    )
    db_session.add(access)
    db_session.flush()

    repository = PropertyAccessRepository(db_session)

    result = repository.get_active_access(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert result is None


def test_get_active_access_returns_none_for_different_access_type(
    db_session,
):
    user = create_user(db_session)
    property = create_property(db_session)

    access = PropertyAccess(
        user_id=user.id,
        property_id=property.id,
        access_type="property_verification",
        is_active=True,
    )
    db_session.add(access)
    db_session.flush()

    repository = PropertyAccessRepository(db_session)

    result = repository.get_active_access(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert result is None


def test_get_by_user_id_returns_all_access_records(db_session):
    user = create_user(db_session)
    property_one = create_property(db_session)
    property_two = create_property(db_session)

    access_one = PropertyAccess(
        user_id=user.id,
        property_id=property_one.id,
        access_type="plate_operations",
        is_active=True,
    )
    access_two = PropertyAccess(
        user_id=user.id,
        property_id=property_two.id,
        access_type="property_verification",
        is_active=True,
    )

    db_session.add_all([access_one, access_two])
    db_session.flush()

    repository = PropertyAccessRepository(db_session)

    result = repository.get_by_user_id(user.id)

    assert len(result) == 2
    assert {access.id for access in result} == {
        access_one.id,
        access_two.id,
    }


def test_deactivate_marks_access_inactive(db_session):
    user = create_user(db_session)
    property = create_property(db_session)

    access = PropertyAccess(
        user_id=user.id,
        property_id=property.id,
        access_type="plate_operations",
        is_active=True,
    )
    db_session.add(access)
    db_session.flush()

    repository = PropertyAccessRepository(db_session)

    result = repository.deactivate(access)

    assert result.id == access.id
    assert result.is_active is False
