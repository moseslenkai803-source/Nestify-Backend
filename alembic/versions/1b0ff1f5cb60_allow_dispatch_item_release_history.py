"""Allow dispatch item release history

Revision ID: 1b0ff1f5cb60
Revises: cb988e5510c6
Create Date: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b0ff1f5cb60"
down_revision: Union[str, Sequence[str], None] = "cb988e5510c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dispatch_items",
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.drop_index(
        "ix_dispatch_items_plate_id",
        table_name="dispatch_items",
    )

    op.create_index(
        "uq_dispatch_items_active_plate_id",
        "dispatch_items",
        ["plate_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_dispatch_items_active_plate_id",
        table_name="dispatch_items",
    )

    op.create_index(
        "ix_dispatch_items_plate_id",
        "dispatch_items",
        ["plate_id"],
        unique=True,
    )

    op.drop_column(
        "dispatch_items",
        "released_at",
    )
