"""add address plate lifecycle event type constraint

Revision ID: 29383571f5ca
Revises: 086476526dfa
Create Date: 2026-09-27 18:05:23.502312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29383571f5ca'
down_revision: Union[str, Sequence[str], None] = '086476526dfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_address_plate_lifecycle_events_event_type",
        "address_plate_lifecycle_events",
        "event_type IN ('manufactured', 'allocated', 'dispatched', 'installed', 'verified', 'activated')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_address_plate_lifecycle_events_event_type",
        "address_plate_lifecycle_events",
        type_="check",
    )
