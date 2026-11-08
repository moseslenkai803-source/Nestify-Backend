"""Validate property location coordinates and accuracy.

Revision ID: c71d4a8b2e90
Revises: a94c2e7d61f0
Create Date: 2026-11-07
"""

from alembic import op


revision = "c71d4a8b2e90"
down_revision = "a94c2e7d61f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_property_locations_latitude_range",
        "property_locations",
        "latitude BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        "ck_property_locations_longitude_range",
        "property_locations",
        "longitude BETWEEN -180 AND 180",
    )
    op.create_check_constraint(
        "ck_property_locations_accuracy_finite_nonnegative",
        "property_locations",
        "accuracy_meters IS NULL OR "
        "(accuracy_meters >= 0 AND "
        "accuracy_meters < 'Infinity'::double precision)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_property_locations_accuracy_finite_nonnegative",
        "property_locations",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_locations_longitude_range",
        "property_locations",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_locations_latitude_range",
        "property_locations",
        type_="check",
    )
