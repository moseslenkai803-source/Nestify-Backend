"""Enforce address plate request status constraint

Revision ID: b35c4e2275cc
Revises: 8254e66ff188
Create Date: 2026-09-27 22:28:29.194098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b35c4e2275cc'
down_revision: Union[str, Sequence[str], None] = '8254e66ff188'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_address_plate_requests_status",
        "address_plate_requests",
        "status IN ('pending', 'approved', 'rejected', 'fulfilled')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_address_plate_requests_status",
        "address_plate_requests",
        type_="check",
    )
