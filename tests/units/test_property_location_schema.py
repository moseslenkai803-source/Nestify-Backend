from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.property_location import PropertyLocationCreate


def valid_payload():
    return {
        "latitude": -1.2921,
        "longitude": 36.8219,
        "source": "device_gps",
        "capture_method": "user_confirmed_device_location",
        "captured_at": datetime.now(UTC),
    }


def test_property_location_schema_accepts_valid_data():
    result = PropertyLocationCreate(**valid_payload())

    assert result.latitude == -1.2921
    assert result.longitude == 36.8219
    assert result.captured_at.tzinfo is not None


@pytest.mark.parametrize(
    "latitude",
    [-90.0001, 90.0001, float("nan"), float("inf"), float("-inf")],
)
def test_property_location_schema_rejects_invalid_latitude(latitude):
    payload = valid_payload()
    payload["latitude"] = latitude

    with pytest.raises(ValidationError):
        PropertyLocationCreate(**payload)


@pytest.mark.parametrize(
    "longitude",
    [-180.0001, 180.0001, float("nan"), float("inf"), float("-inf")],
)
def test_property_location_schema_rejects_invalid_longitude(longitude):
    payload = valid_payload()
    payload["longitude"] = longitude

    with pytest.raises(ValidationError):
        PropertyLocationCreate(**payload)


@pytest.mark.parametrize(
    "accuracy",
    [-0.001, float("nan"), float("inf"), float("-inf")],
)
def test_property_location_schema_rejects_invalid_accuracy(accuracy):
    payload = valid_payload()
    payload["accuracy_meters"] = accuracy

    with pytest.raises(ValidationError):
        PropertyLocationCreate(**payload)


def test_property_location_schema_accepts_null_accuracy():
    payload = valid_payload()
    payload["accuracy_meters"] = None

    result = PropertyLocationCreate(**payload)

    assert result.accuracy_meters is None


def test_property_location_schema_rejects_naive_captured_at():
    payload = valid_payload()
    payload["captured_at"] = datetime(2026, 11, 7, 12, 0, 0)

    with pytest.raises(ValidationError, match="timezone-aware"):
        PropertyLocationCreate(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", ""),
        ("source", "   "),
        ("source", "x" * 51),
        ("capture_method", ""),
        ("capture_method", "   "),
        ("capture_method", "x" * 101),
    ],
)
def test_property_location_schema_rejects_invalid_provenance(field, value):
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        PropertyLocationCreate(**payload)
