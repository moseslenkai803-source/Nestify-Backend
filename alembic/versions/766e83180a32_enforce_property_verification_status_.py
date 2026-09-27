"""Enforce property verification status constraint

Revision ID: 766e83180a32
Revises: 29383571f5ca
Create Date: 2026-09-27 18:35:38.977637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '766e83180a32'
down_revision: Union[str, Sequence[str], None] = '29383571f5ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_property_verifications_status",
        "property_verifications",
        "status IN (\x27verified\x27, \x27rejected\x27)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_property_verifications_status",
        "property_verifications",
        type_="check",
    )
