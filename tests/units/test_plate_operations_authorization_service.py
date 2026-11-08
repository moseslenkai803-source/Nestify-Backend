from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.plate_operations_authorization_service import (
    PlateOperationsAuthorizationService,
)


def _authorization_service():
    service = object.__new__(PlateOperationsAuthorizationService)
    service.user_repository = Mock()
    service.employee_repository = Mock()
    service.employee_clearance_repository = Mock()
    service.property_authorization_service = SimpleNamespace(
        property_repository=Mock(),
        property_access_repository=Mock(),
    )
    return service


def test_plate_operations_authorization_rejects_stale_clearance():
    service = _authorization_service()
    user_id = uuid4()
    employee = SimpleNamespace(id=uuid4(), ended_at=None)
    user = SimpleNamespace(
        id=user_id,
        role="employee",
        is_active=True,
    )
    service.user_repository.get_by_id.return_value = user
    service.user_repository.get_by_id_for_update.return_value = user
    service.employee_repository.get_by_user_id_for_update.return_value = (
        employee
    )
    service.employee_clearance_repository.get_by_employee_and_clearance.return_value = (
        SimpleNamespace(is_active=True)
    )
    service.employee_clearance_repository.get_by_employee_and_clearance_for_update.return_value = (
        SimpleNamespace(is_active=False)
    )

    with pytest.raises(
        ValueError,
        match="Active plate_operations employee clearance is required",
    ):
        service.require_authorized_user(user_id)

    service.employee_repository.get_by_user_id_for_update.assert_called_once_with(
        user_id
    )
    service.user_repository.get_by_id_for_update.assert_called_once_with(
        user_id
    )
    service.employee_clearance_repository.get_by_employee_and_clearance_for_update.assert_called_once_with(
        employee.id,
        "plate_operations",
    )
    service.employee_clearance_repository.get_by_employee_and_clearance.assert_not_called()


def test_plate_operations_authorization_rejects_stale_property_grant():
    service = _authorization_service()
    user_id = uuid4()
    property_id = uuid4()
    user = SimpleNamespace(id=user_id, role="employee")
    property_record = SimpleNamespace(id=property_id)
    access_repository = (
        service.property_authorization_service.property_access_repository
    )
    service.require_authorized_user = Mock(return_value=user)
    service.property_authorization_service.property_repository.get_by_id.return_value = (
        property_record
    )
    access_repository.get_active_access.return_value = SimpleNamespace(
        is_active=True
    )
    access_repository.get_by_user_property_type_for_update.return_value = (
        SimpleNamespace(is_active=False)
    )

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.authorize_property(user_id, property_id)

    access_repository.get_by_user_property_type_for_update.assert_called_once()
    access_repository.get_active_access.assert_not_called()


def test_administrator_plate_operations_keep_property_grant_exception():
    service = _authorization_service()
    user = SimpleNamespace(id=uuid4(), role="admin")
    property_id = uuid4()
    property_record = SimpleNamespace(id=property_id)
    access_repository = (
        service.property_authorization_service.property_access_repository
    )
    service.require_authorized_user = Mock(return_value=user)
    service.property_authorization_service.property_repository.get_by_id.return_value = (
        property_record
    )

    assert service.authorize_property(user.id, property_id) is property_record
    access_repository.get_by_user_property_type_for_update.assert_not_called()
