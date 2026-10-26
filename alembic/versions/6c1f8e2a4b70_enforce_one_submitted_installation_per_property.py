"""enforce one submitted installation per property

Revision ID: 6c1f8e2a4b70
Revises: 0154bb05e6fd
Create Date: 2026-10-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c1f8e2a4b70"
down_revision: Union[str, Sequence[str], None] = "0154bb05e6fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_property_installations_one_submitted_per_property"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "property_installations",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text("status = 'submitted'"),
    )


def downgrade() -> None:
    op.drop_index(
        INDEX_NAME,
        table_name="property_installations",
    )
