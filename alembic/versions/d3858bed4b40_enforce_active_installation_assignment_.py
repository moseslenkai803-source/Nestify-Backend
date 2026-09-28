"""Enforce active installation assignment uniqueness

Revision ID: d3858bed4b40
Revises: 1bd5872c23ae
Create Date: 2026-09-28 20:47:34.924777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3858bed4b40'
down_revision: Union[str, Sequence[str], None] = '1bd5872c23ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_installation_assignments_active_property",
        "installation_assignments",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('assigned', 'in_progress', 'submitted')"
        ),
    )

    op.create_index(
        "uq_installation_assignments_active_plate",
        "installation_assignments",
        ["plate_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('assigned', 'in_progress', 'submitted')"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_installation_assignments_active_plate",
        table_name="installation_assignments",
    )
    op.drop_index(
        "uq_installation_assignments_active_property",
        table_name="installation_assignments",
    )
