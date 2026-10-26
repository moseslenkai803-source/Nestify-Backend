"""add manufacturing order cancellation audit

Revision ID: 4a7c9e2d1f60
Revises: ec18197d65ef
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4a7c9e2d1f60"
down_revision: Union[str, Sequence[str], None] = "ec18197d65ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "manufacturing_orders",
        sa.Column("cancelled_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "manufacturing_orders",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "manufacturing_orders",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_manufacturing_orders_cancelled_by_users",
        "manufacturing_orders",
        "users",
        ["cancelled_by"],
        ["id"],
    )
    op.create_index(
        "ix_manufacturing_orders_cancelled_by",
        "manufacturing_orders",
        ["cancelled_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_manufacturing_orders_cancelled_by",
        table_name="manufacturing_orders",
    )
    op.drop_constraint(
        "fk_manufacturing_orders_cancelled_by_users",
        "manufacturing_orders",
        type_="foreignkey",
    )
    op.drop_column("manufacturing_orders", "cancellation_reason")
    op.drop_column("manufacturing_orders", "cancelled_at")
    op.drop_column("manufacturing_orders", "cancelled_by")
