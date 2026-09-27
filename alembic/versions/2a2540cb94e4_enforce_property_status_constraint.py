"""enforce property status constraint

Revision ID: 2a2540cb94e4
Revises: b35c4e2275cc
Create Date: 2026-09-27 22:45:22.150053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a2540cb94e4'
down_revision: Union[str, Sequence[str], None] = 'b35c4e2275cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_properties_status",
        "properties",
        "status IN ('draft', 'verified', 'active')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_properties_status",
        "properties",
        type_="check",
    )
