"""Validate property installation coordinates and accuracy.

Revision ID: d6a9f2c41b70
Revises: c71d4a8b2e90
Create Date: 2026-11-08
"""

from alembic import op


revision = "d6a9f2c41b70"
down_revision = "c71d4a8b2e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_property_installations_latitude_range",
        "property_installations",
        "latitude BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        "ck_property_installations_longitude_range",
        "property_installations",
        "longitude BETWEEN -180 AND 180",
    )
    op.create_check_constraint(
        "ck_property_installations_accuracy_finite_nonnegative",
        "property_installations",
        "accuracy_meters IS NULL OR "
        "(accuracy_meters >= 0 AND "
        "accuracy_meters < 'Infinity'::double precision)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_property_installations_accuracy_finite_nonnegative",
        "property_installations",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_installations_longitude_range",
        "property_installations",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_installations_latitude_range",
        "property_installations",
        type_="check",
    )
