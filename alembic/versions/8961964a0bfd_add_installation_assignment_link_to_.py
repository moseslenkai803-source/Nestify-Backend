"""add installation assignment link to property installations

Revision ID: 8961964a0bfd
Revises: d3858bed4b40
Create Date: 2026-09-28 22:41:57.105498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8961964a0bfd'
down_revision: Union[str, Sequence[str], None] = 'd3858bed4b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "property_installations",
        sa.Column(
            "assignment_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_property_installations_assignment_id",
        "property_installations",
        ["assignment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_property_installations_assignment_id",
        "property_installations",
        "installation_assignments",
        ["assignment_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_property_installations_assignment_id",
        "property_installations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_property_installations_assignment_id",
        table_name="property_installations",
    )
    op.drop_column(
        "property_installations",
        "assignment_id",
    )
