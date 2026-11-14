"""Add persisted platform settings and audit history.

Revision ID: f4b2c8d91a63
Revises: d6a9f2c41b70
Create Date: 2026-11-14
"""

from alembic import op
import sqlalchemy as sa


revision = "f4b2c8d91a63"
down_revision = "d6a9f2c41b70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("support_email", sa.String(length=255), nullable=True),
        sa.Column("support_phone", sa.String(length=30), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("date_format", sa.String(length=20), nullable=False),
        sa.Column("time_format", sa.String(length=10), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
        sa.CheckConstraint(
            "length(currency_code) = 3 "
            "AND currency_code = upper(currency_code)",
            name="ck_platform_settings_currency_code",
        ),
        sa.CheckConstraint(
            "time_format IN ('12h', '24h')",
            name="ck_platform_settings_time_format",
        ),
        sa.CheckConstraint(
            "date_format IN ('DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD')",
            name="ck_platform_settings_date_format",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "platform_setting_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_platform_setting_audit_logs_changed_at",
        "platform_setting_audit_logs",
        ["changed_at"],
    )
    op.create_index(
        "ix_platform_setting_audit_logs_setting_key",
        "platform_setting_audit_logs",
        ["setting_key"],
    )
    op.create_index(
        "ix_platform_setting_audit_logs_actor_user_id",
        "platform_setting_audit_logs",
        ["actor_user_id"],
    )

    # Audit history is append-only: reject row mutations and table truncation.
    op.execute(
        """
        CREATE FUNCTION prevent_platform_setting_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'platform_setting_audit_logs is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_platform_setting_audit_no_mutation
        BEFORE UPDATE OR DELETE ON platform_setting_audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_platform_setting_audit_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_platform_setting_audit_no_truncate
        BEFORE TRUNCATE ON platform_setting_audit_logs
        FOR EACH STATEMENT
        EXECUTE FUNCTION prevent_platform_setting_audit_mutation()
        """
    )

    op.execute(
        sa.text(
            """
            INSERT INTO platform_settings (
                id,
                organization_name,
                legal_name,
                support_email,
                support_phone,
                timezone,
                locale,
                currency_code,
                date_format,
                time_format,
                updated_by,
                created_at,
                updated_at
            )
            VALUES (
                1,
                'Nestify',
                NULL,
                NULL,
                NULL,
                'Africa/Nairobi',
                'en-KE',
                'KES',
                'DD/MM/YYYY',
                '24h',
                NULL,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("platform_setting_audit_logs")
    op.execute("DROP FUNCTION prevent_platform_setting_audit_mutation()")
    op.drop_table("platform_settings")
