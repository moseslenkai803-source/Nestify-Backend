"""Add password reset tokens and generalize email outbox events.

Revision ID: b7e2c91a5f40
Revises: f4b2c8d91a63
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e2c91a5f40"
down_revision = "f4b2c8d91a63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve the invitation ID column and all existing values.
    op.drop_constraint(
        "email_outbox_employee_invitation_id_fkey",
        "email_outbox",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_email_outbox_employee_invitation_id",
        table_name="email_outbox",
    )
    op.alter_column(
        "email_outbox",
        "employee_invitation_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_consumed",
        "password_reset_tokens",
        ["user_id", "consumed_at"],
        unique=False,
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    # Refuse to discard password-reset outbox rows or their NULL invitation IDs.
    connection = op.get_bind()
    null_invitation_rows = connection.scalar(
        sa.text(
            "SELECT count(*) FROM email_outbox "
            "WHERE employee_invitation_id IS NULL"
        )
    )
    if null_invitation_rows:
        raise RuntimeError(
            "Cannot downgrade: email_outbox contains rows without "
            "employee_invitation_id."
        )

    reset_token_rows = connection.scalar(
        sa.text("SELECT count(*) FROM password_reset_tokens")
    )
    if reset_token_rows:
        raise RuntimeError(
            "Cannot downgrade: password_reset_tokens contains records."
        )

    op.drop_index(
        "ix_password_reset_tokens_expires_at",
        table_name="password_reset_tokens",
    )
    op.drop_index(
        "ix_password_reset_tokens_user_consumed",
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")

    op.alter_column(
        "email_outbox",
        "employee_invitation_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_index(
        "ix_email_outbox_employee_invitation_id",
        "email_outbox",
        ["employee_invitation_id"],
        unique=False,
    )
    op.create_foreign_key(
        "email_outbox_employee_invitation_id_fkey",
        "email_outbox",
        "employee_invitations",
        ["employee_invitation_id"],
        ["id"],
        ondelete="CASCADE",
    )
