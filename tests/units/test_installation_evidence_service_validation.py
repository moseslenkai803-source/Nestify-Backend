from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.services.installation_assignment_service import (
    InstallationAssignmentService,
)
from app.services.property_installation_service import (
    PropertyInstallationService,
)


SERVICE_METHODS = [
    (
        PropertyInstallationService,
        "create_installation",
        {
            "property_id": uuid4(),
            "plate_id": uuid4(),
            "installer_id": uuid4(),
        },
    ),
    (
        InstallationAssignmentService,
        "submit_assignment",
        {
            "assignment_id": uuid4(),
            "contractor_user_id": uuid4(),
        },
    ),
]


def valid_evidence():
    return {
        "latitude": -1.2921,
        "longitude": 36.8219,
        "accuracy_meters": 4.5,
        "captured_at": datetime.now(UTC),
    }


@pytest.mark.parametrize(
    ("latitude", "message"),
    [
        (-90.0001, "Latitude must be between -90 and 90"),
        (90.0001, "Latitude must be between -90 and 90"),
        (float("nan"), "Latitude must be finite"),
        (float("inf"), "Latitude must be finite"),
        (float("-inf"), "Latitude must be finite"),
    ],
)
@pytest.mark.parametrize(("service_class", "method_name", "ids"), SERVICE_METHODS)
def test_services_reject_invalid_latitude_before_repository_access(
    service_class,
    method_name,
    ids,
    latitude,
    message,
):
    service = service_class.__new__(service_class)
    evidence = valid_evidence()
    evidence["latitude"] = latitude

    with pytest.raises(ValueError, match=message):
        getattr(service, method_name)(**ids, **evidence)


@pytest.mark.parametrize(
    ("longitude", "message"),
    [
        (-180.0001, "Longitude must be between -180 and 180"),
        (180.0001, "Longitude must be between -180 and 180"),
        (float("nan"), "Longitude must be finite"),
        (float("inf"), "Longitude must be finite"),
        (float("-inf"), "Longitude must be finite"),
    ],
)
@pytest.mark.parametrize(("service_class", "method_name", "ids"), SERVICE_METHODS)
def test_services_reject_invalid_longitude_before_repository_access(
    service_class,
    method_name,
    ids,
    longitude,
    message,
):
    service = service_class.__new__(service_class)
    evidence = valid_evidence()
    evidence["longitude"] = longitude

    with pytest.raises(ValueError, match=message):
        getattr(service, method_name)(**ids, **evidence)


@pytest.mark.parametrize(
    "accuracy",
    [-0.001, float("nan"), float("inf"), float("-inf")],
)
@pytest.mark.parametrize(("service_class", "method_name", "ids"), SERVICE_METHODS)
def test_services_reject_invalid_accuracy_before_repository_access(
    service_class,
    method_name,
    ids,
    accuracy,
):
    service = service_class.__new__(service_class)
    evidence = valid_evidence()
    evidence["accuracy_meters"] = accuracy

    expected = (
        "Accuracy must be finite"
        if accuracy != accuracy or accuracy in (float("inf"), float("-inf"))
        else "Accuracy must be greater than or equal to 0"
    )

    with pytest.raises(ValueError, match=expected):
        getattr(service, method_name)(**ids, **evidence)


@pytest.mark.parametrize(("service_class", "method_name", "ids"), SERVICE_METHODS)
def test_services_reject_naive_timestamp_before_repository_access(
    service_class,
    method_name,
    ids,
):
    service = service_class.__new__(service_class)
    evidence = valid_evidence()
    evidence["captured_at"] = datetime(2026, 11, 7, 12, 0, 0)

    with pytest.raises(
        ValueError,
        match="Captured timestamp must be timezone-aware",
    ):
        getattr(service, method_name)(**ids, **evidence)
