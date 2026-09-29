"""enforce property access type

Revision ID: d7221bbb2a82
Revises: 59761e2a54ef
Create Date: 2026-09-29 12:41:40.204717

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd7221bbb2a82'
down_revision: Union[str, Sequence[str], None] = '59761e2a54ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_property_access_access_type",
        "property_access",
        type_="check",
    )
