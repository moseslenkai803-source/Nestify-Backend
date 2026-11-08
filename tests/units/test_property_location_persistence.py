import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.models.property_location import PropertyLocation
from app.models.property_location_verification import (
    PropertyLocationVerification,
)


def _constraints(model):
    return {
        constraint.name: constraint
        for constraint in model.__table__.constraints
    }


def test_property_location_persistence_constraints():
    constraints = _constraints(PropertyLocation)

    assert isinstance(
        constraints["uq_property_locations_property_version"],
        UniqueConstraint,
    )
    assert isinstance(
        constraints["ck_property_locations_version_number_positive"],
        CheckConstraint,
    )
    assert isinstance(
        constraints["ck_property_locations_status"],
        CheckConstraint,
    )
    assert isinstance(
        constraints["ck_property_locations_current_requires_approval"],
        CheckConstraint,
    )
    assert str(constraints["ck_property_locations_version_number_positive"].sqltext) == (
        "version_number > 0"
    )
    assert str(constraints["ck_property_locations_status"].sqltext) == (
        "status IN ('unverified', 'pending', 'approved', 'rejected')"
    )
    assert str(
        constraints["ck_property_locations_current_requires_approval"].sqltext
    ) == "NOT is_current OR status = 'approved'"

    indexes = {
        index.name: index
        for index in PropertyLocation.__table__.indexes
    }
    assert not indexes["ix_property_locations_property_id"].unique
    assert indexes[
        "uq_property_locations_one_pending_per_property"
    ].unique
    assert str(
        indexes[
            "uq_property_locations_one_pending_per_property"
        ].dialect_options["postgresql"]["where"].compile(
            dialect=postgresql.dialect()
        )
    ) == "status = 'pending'"
    assert indexes[
        "uq_property_locations_one_current_per_property"
    ].unique
    assert str(
        indexes[
            "uq_property_locations_one_current_per_property"
        ].dialect_options["postgresql"]["where"].compile(
            dialect=postgresql.dialect()
        )
    ) == "is_current IS TRUE"

    assert PropertyLocation.__table__.c.version_number.nullable is False
    assert PropertyLocation.__table__.c.version_number.default.arg == 1
    assert PropertyLocation.__table__.c.submitted_by_id.nullable is True
    assert PropertyLocation.__table__.c.submitted_at.nullable is True
    assert PropertyLocation.__table__.c.is_current.nullable is False
    assert PropertyLocation.__table__.c.is_current.default.arg is False


def test_property_location_foreign_keys_restrict_deletion():
    foreign_keys = {
        foreign_key.parent.name: foreign_key
        for foreign_key in PropertyLocation.__table__.foreign_keys
    }

    assert foreign_keys["property_id"].ondelete == "RESTRICT"
    assert foreign_keys["submitted_by_id"].ondelete == "RESTRICT"


def test_property_location_verification_persistence_constraints():
    constraints = _constraints(PropertyLocationVerification)

    assert isinstance(
        constraints["uq_property_location_verifications_location"],
        UniqueConstraint,
    )
    assert isinstance(
        constraints["ck_property_location_verifications_decision"],
        CheckConstraint,
    )
    assert str(
        constraints["ck_property_location_verifications_decision"].sqltext
    ) == "decision IN ('approved', 'rejected')"

    foreign_keys = {
        foreign_key.parent.name: foreign_key
        for foreign_key in PropertyLocationVerification.__table__.foreign_keys
    }
    assert foreign_keys["location_id"].ondelete == "RESTRICT"
    assert foreign_keys["verified_by"].ondelete == "RESTRICT"


@pytest.mark.parametrize(
    ("name", "expected_sql"),
    [
        (
            "ck_property_locations_latitude_range",
            "latitude BETWEEN -90 AND 90",
        ),
        (
            "ck_property_locations_longitude_range",
            "longitude BETWEEN -180 AND 180",
        ),
        (
            "ck_property_locations_accuracy_finite_nonnegative",
            "accuracy_meters IS NULL OR "
            "(accuracy_meters >= 0 AND "
            "accuracy_meters < 'Infinity'::double precision)",
        ),
    ],
)
def test_property_location_coordinate_constraints(name, expected_sql):
    constraints = _constraints(PropertyLocation)

    assert isinstance(constraints[name], CheckConstraint)
    assert str(constraints[name].sqltext) == expected_sql
