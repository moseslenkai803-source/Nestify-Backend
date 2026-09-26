"""Remove legacy address plate verified timestamp

Revision ID: 3ed9f39347bb
Revises: 8cfb0dbd300f
Create Date: 2026-09-26 16:04:33.432554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ed9f39347bb'
down_revision: Union[str, Sequence[str], None] = '8cfb0dbd300f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("address_plates", "verified_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "address_plates",
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
