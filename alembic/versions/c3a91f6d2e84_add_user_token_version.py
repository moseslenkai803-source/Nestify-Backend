"""Add account token version for JWT invalidation.

Revision ID: c3a91f6d2e84
Revises: b7e2c91a5f40
"""

from alembic import op
import sqlalchemy as sa


revision = "c3a91f6d2e84"
down_revision = "b7e2c91a5f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()

    nonzero_versions = connection.scalar(
        sa.text(
            "SELECT count(*) FROM users WHERE token_version <> 0"
        )
    )

    if nonzero_versions:
        raise RuntimeError(
            "Cannot downgrade: users contain nonzero token versions."
        )

    op.drop_column("users", "token_version")
