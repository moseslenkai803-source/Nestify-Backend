"""add property plate request access type

Revision ID: 2499f1e16422
Revises: d7221bbb2a82
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op


revision: str = "2499f1e16422"
down_revision: Union[str, Sequence[str], None] = "d7221bbb2a82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_property_access_access_type",
        "property_access",
        type_="check",
    )

    op.create_check_constraint(
        "ck_property_access_access_type",
        "property_access",
        "access_type IN ("
        "'property_management', "
        "'plate_request', "
        "'plate_operations', "
        "'property_verification', "
        "'installation_verification'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_property_access_access_type",
        "property_access",
        type_="check",
    )

    op.create_check_constraint(
        "ck_property_access_access_type",
        "property_access",
        "access_type IN ("
        "'property_management', "
        "'plate_operations', "
        "'property_verification', "
        "'installation_verification'"
        ")",
    )
