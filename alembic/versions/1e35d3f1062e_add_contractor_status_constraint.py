"""Add contractor status constraint

Revision ID: 1e35d3f1062e
Revises: c8e99868c180
Create Date: 2026-09-30 18:23:15.349495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e35d3f1062e'
down_revision: Union[str, Sequence[str], None] = 'c8e99868c180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_contractors_status",
        "contractors",
        "status IN ('active', 'inactive')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_contractors_status",
        "contractors",
        type_="check",
    )
