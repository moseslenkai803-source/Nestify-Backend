import uuid
from datetime import UTC, datetime

import pytest

from app.models.employee import Employee
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.user import User
from app.services.property_access_service import PropertyAccessService


def create_user(
    db_session,
    role="employee",
    create_employee_record=True,
):
    user = User(
        email=f"property-access-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    if role == "employee" and create_employee_record:
        employee = Employee(
            user_id=user.id,
            employee_number=f"PA-{uuid.uuid4().hex[:20].upper()}",
            department="Operations",
            position="Test Employee",
        )
        db_session.add(employee)
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


def test_authorize_rejects_missing_employee_record(db_session):
    employee = create_user(
        db_session,
        create_employee_record=False,
    )
    property = create_property(db_session)
    service = PropertyAccessService(db_session)

    with pytest.raises(ValueError, match="Employee record not found"):
        service.authorize(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_authorize_rejects_terminated_employee_with_active_account(
    db_session,
):
    employee = create_user(db_session)
    property = create_property(db_session)
    service = PropertyAccessService(db_session)

    # Create a valid grant while the employee is still active.
    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    # Simulate termination without deactivating the account or old grant.
    employee_record = (
        db_session.query(Employee)
        .filter(Employee.user_id == employee.id)
        .one()
    )
    employee_record.ended_at = datetime.now(UTC)
    db_session.flush()

    with pytest.raises(ValueError, match="Employee is terminated"):
        service.authorize(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_authorize_rejects_inactive_employee_account(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)
    employee.is_active = False
    db_session.flush()
    service = PropertyAccessService(db_session)

    with pytest.raises(ValueError, match="Employee is inactive"):
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


def test_grant_access_reactivates_inactive_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    granted_access = service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    service.revoke_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    reactivated_access = service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    assert reactivated_access.id == granted_access.id
    assert reactivated_access.is_active is True


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


def test_grant_access_rejects_invalid_access_type(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Invalid property access type",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="invalid_access",
        )


def test_grant_access_rejects_missing_user(db_session):
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Employee not found",
    ):
        service.grant_access(
            user_id=uuid.uuid4(),
            property_id=property.id,
            access_type="plate_operations",
        )


def test_grant_access_rejects_inactive_user(db_session):
    employee = create_user(db_session)
    employee.is_active = False
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Employee is inactive",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_grant_access_rejects_non_employee_user(db_session):
    landlord = create_user(
        db_session,
        role="landlord",
    )
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="User must be an employee",
    ):
        service.grant_access(
            user_id=landlord.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_grant_access_rejects_missing_employee_record(db_session):
    employee = create_user(
        db_session,
        create_employee_record=False,
    )
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Employee record not found",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_grant_access_rejects_terminated_employee(db_session):
    employee = create_user(db_session)
    employee_record = (
        db_session.query(Employee)
        .filter(Employee.user_id == employee.id)
        .one()
    )
    employee_record.ended_at = datetime.now(UTC)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Employee is terminated",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_revoke_access_rejects_already_inactive_access(db_session):
    employee = create_user(db_session)
    property = create_property(db_session)
    service = PropertyAccessService(db_session)

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )
    service.revoke_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    with pytest.raises(
        ValueError,
        match="Active property access not found",
    ):
        service.revoke_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )


def test_grant_access_rejects_missing_property(db_session):
    employee = create_user(db_session)

    service = PropertyAccessService(db_session)

    with pytest.raises(
        ValueError,
        match="Property not found",
    ):
        service.grant_access(
            user_id=employee.id,
            property_id=uuid.uuid4(),
            access_type="plate_operations",
        )

def test_list_accessible_properties_returns_active_properties(
    db_session,
):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    result = service.list_accessible_properties(employee.id)

    assert len(result) == 1
    assert result[0].id == property.id


def test_list_accessible_properties_excludes_inactive_access(
    db_session,
):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    service.revoke_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    result = service.list_accessible_properties(employee.id)

    assert result == []


def test_list_accessible_properties_deduplicates_multiple_access_types(
    db_session,
):
    employee = create_user(db_session)
    property = create_property(db_session)

    service = PropertyAccessService(db_session)

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    service.grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="property_verification",
    )

    result = service.list_accessible_properties(employee.id)

    assert len(result) == 1
    assert result[0].id == property.id


def test_list_accessible_properties_rejects_user_without_employee_record(
    db_session,
):
    user = create_user(db_session, create_employee_record=False)
    service = PropertyAccessService(db_session)

    with pytest.raises(ValueError, match="Employee record not found"):
        service.list_accessible_properties(user.id)


def test_list_accessible_properties_rejects_terminated_employee(
    db_session,
):
    user = create_user(db_session)
    employee = (
        db_session.query(Employee)
        .filter(Employee.user_id == user.id)
        .one()
    )
    employee.ended_at = datetime.now(UTC)
    db_session.flush()

    service = PropertyAccessService(db_session)

    with pytest.raises(ValueError, match="Employee is terminated"):
        service.list_accessible_properties(user.id)


def test_list_accessible_properties_rejects_inactive_user(
    db_session,
):
    user = create_user(db_session)
    user.is_active = False
    db_session.flush()

    service = PropertyAccessService(db_session)

    with pytest.raises(ValueError, match="Employee is inactive"):
        service.list_accessible_properties(user.id)


def test_list_accessible_properties_rejects_non_employee_role(
    db_session,
):
    user = create_user(db_session, role="landlord")
    service = PropertyAccessService(db_session)

    with pytest.raises(ValueError, match="User must be an employee"):
        service.list_accessible_properties(user.id)
