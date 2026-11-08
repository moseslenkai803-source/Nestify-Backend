from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.installation_assignment import InstallationAssignmentSubmit
from app.schemas.property_installation import PropertyInstallationCreate


SCHEMAS = [
    PropertyInstallationCreate,
    InstallationAssignmentSubmit,
]


def valid_payload():
    payload = {
        "latitude": -1.2921,
        "longitude": 36.8219,
        "accuracy_meters": 4.5,
        "captured_at": datetime.now(UTC),
        "notes": "Installation evidence",
    }
    if "plate_id" in PropertyInstallationCreate.model_fields:
        payload["plate_id"] = "a1b2c3d4-3000-4000-8000-000000000001"
    return payload


@pytest.mark.parametrize("schema", SCHEMAS)
def test_installation_evidence_schema_accepts_valid_data(schema):
    result = schema(**valid_payload())

    assert result.latitude == -1.2921
    assert result.longitude == 36.8219
    assert result.accuracy_meters == 4.5
    assert result.captured_at.utcoffset() is not None


@pytest.mark.parametrize("schema", SCHEMAS)
@pytest.mark.parametrize(
    "latitude",
    [-90.0001, 90.0001, float("nan"), float("inf"), float("-inf")],
)
def test_installation_evidence_schema_rejects_invalid_latitude(
    schema,
    latitude,
):
    payload = valid_payload()
    payload["latitude"] = latitude

    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize("schema", SCHEMAS)
@pytest.mark.parametrize(
    "longitude",
    [-180.0001, 180.0001, float("nan"), float("inf"), float("-inf")],
)
def test_installation_evidence_schema_rejects_invalid_longitude(
    schema,
    longitude,
):
    payload = valid_payload()
    payload["longitude"] = longitude

    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize("schema", SCHEMAS)
@pytest.mark.parametrize(
    "accuracy",
    [-0.001, float("nan"), float("inf"), float("-inf")],
)
def test_installation_evidence_schema_rejects_invalid_accuracy(
    schema,
    accuracy,
):
    payload = valid_payload()
    payload["accuracy_meters"] = accuracy

    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize("schema", SCHEMAS)
def test_installation_evidence_schema_accepts_null_accuracy(schema):
    payload = valid_payload()
    payload["accuracy_meters"] = None

    result = schema(**payload)

    assert result.accuracy_meters is None


@pytest.mark.parametrize("schema", SCHEMAS)
def test_installation_evidence_schema_rejects_naive_timestamp(schema):
    payload = valid_payload()
    payload["captured_at"] = datetime(2026, 11, 7, 12, 0, 0)

    with pytest.raises(ValidationError, match="timezone-aware"):
        schema(**payload)
