"""Enforce property installation status constraints

Revision ID: 43a49dd80653
Revises: 766e83180a32
Create Date: 2026-09-27 20:57:33.580102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "43a49dd80653"
down_revision: Union[str, Sequence[str], None] = "766e83180a32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_property_installations_status",
        "property_installations",
        "status IN ('submitted', 'verified', 'rejected')",
    )
    op.create_check_constraint(
        "ck_property_installation_verifications_status",
        "property_installation_verifications",
        "status IN ('verified', 'rejected')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_property_installation_verifications_status",
        "property_installation_verifications",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_installations_status",
        "property_installations",
        type_="check",
    )
