import uuid

import pytest
from fastapi import HTTPException

from app.api.dependencies import get_current_landlord, get_current_user, require_employee_clearance
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


def test_inactive_user_is_rejected():
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=False,
    )

    from unittest.mock import Mock, patch

    credentials = Mock()
    credentials.credentials = "test-token"

    db = Mock()

    with patch(
        "app.api.dependencies.decode_access_token",
        return_value={"sub": str(user.id)},
    ):
        db_user_repository = db

        with patch(
            "app.api.dependencies.UserRepository",
        ) as repository_class:
            repository_class.return_value.get_by_id.return_value = user

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(
                    credentials=credentials,
                    db=db_user_repository,
                )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User account is inactive"


def test_current_landlord_returns_landlord_profile():
    user = User(
        id=uuid.uuid4(),
        email="landlord@example.com",
        password_hash="test-hash",
        role="landlord",
        is_active=True,
    )

    landlord = object()

    db = __import__("unittest").mock.Mock()

    with __import__("unittest").mock.patch(
        "app.api.dependencies.LandlordRepository",
    ) as repository_class:
        repository_class.return_value.get_by_user_id.return_value = landlord

        result = get_current_landlord(
            current_user=user,
            db=db,
        )

    assert result is landlord
    repository_class.return_value.get_by_user_id.assert_called_once_with(
        user.id,
    )


def test_current_landlord_rejects_user_without_landlord_profile():
    user = User(
        id=uuid.uuid4(),
        email="customer@example.com",
        password_hash="test-hash",
        role="customer",
        is_active=True,
    )

    db = __import__("unittest").mock.Mock()

    with __import__("unittest").mock.patch(
        "app.api.dependencies.LandlordRepository",
    ) as repository_class:
        repository_class.return_value.get_by_user_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_landlord(
                current_user=user,
                db=db,
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Landlord profile not found"


def test_invalid_access_token_is_rejected():
    from unittest.mock import Mock, patch

    credentials = Mock()
    credentials.credentials = "invalid-token"

    with patch(
        "app.api.dependencies.decode_access_token",
        side_effect=Exception("token validation failed"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                credentials=credentials,
                db=Mock(),
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


def test_access_token_without_subject_is_rejected():
    from unittest.mock import Mock, patch

    credentials = Mock()
    credentials.credentials = "token-without-sub"

    with patch(
        "app.api.dependencies.decode_access_token",
        return_value={},
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                credentials=credentials,
                db=Mock(),
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


def test_access_token_with_invalid_subject_uuid_is_rejected():
    from unittest.mock import Mock, patch

    credentials = Mock()
    credentials.credentials = "token-with-invalid-sub"

    with patch(
        "app.api.dependencies.decode_access_token",
        return_value={"sub": "not-a-uuid"},
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                credentials=credentials,
                db=Mock(),
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


def test_access_token_for_missing_user_is_rejected():
    from unittest.mock import Mock, patch

    credentials = Mock()
    credentials.credentials = "token-for-missing-user"

    missing_user_id = uuid.uuid4()

    with patch(
        "app.api.dependencies.decode_access_token",
        return_value={"sub": str(missing_user_id)},
    ):
        with patch(
            "app.api.dependencies.UserRepository",
        ) as repository_class:
            repository_class.return_value.get_by_id.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(
                    credentials=credentials,
                    db=Mock(),
                )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found"
