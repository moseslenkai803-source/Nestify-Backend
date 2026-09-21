import pytest
from fastapi import HTTPException

from app.api.dependencies import require_employee_clearance
from app.models.user import User


def test_employee_with_required_clearance_is_allowed():
    user = User(
        email="employee@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    dependency = require_employee_clearance("plate_operations")

    result = dependency(user)

    assert result is user


def test_employee_with_wrong_clearance_is_rejected():
    user = User(
        email="employee@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="support",
        is_active=True,
    )

    dependency = require_employee_clearance("plate_operations")

    with pytest.raises(HTTPException) as exc_info:
        dependency(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient employee clearance"


def test_landlord_is_rejected_from_employee_clearance():
    user = User(
        email="landlord@example.com",
        password_hash="test-hash",
        role="landlord",
        clearance="plate_operations",
        is_active=True,
    )

    dependency = require_employee_clearance("plate_operations")

    with pytest.raises(HTTPException) as exc_info:
        dependency(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Employee access required"
