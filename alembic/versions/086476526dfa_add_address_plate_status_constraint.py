"""add address plate status constraint

Revision ID: 086476526dfa
Revises: 3ed9f39347bb
Create Date: 2026-09-27 17:48:01.159161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '086476526dfa'
down_revision: Union[str, Sequence[str], None] = '3ed9f39347bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_address_plates_status",
        "address_plates",
        "status IN ('unactivated', 'active')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_address_plates_status",
        "address_plates",
        type_="check",
    )
