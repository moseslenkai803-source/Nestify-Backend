"""Enforce property location status constraint

Revision ID: 8254e66ff188
Revises: 43a49dd80653
Create Date: 2026-09-27 21:37:32.478256

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8254e66ff188"
down_revision: Union[str, Sequence[str], None] = "43a49dd80653"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_property_locations_status",
        "property_locations",
        "status IN ('unverified')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_property_locations_status",
        "property_locations",
        type_="check",
    )
