"""Version property locations and add location verification decisions.

Revision ID: a94c2e7d61f0
Revises: 6c1f8e2a4b70
Create Date: 2026-11-05
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a94c2e7d61f0"
down_revision: Union[str, Sequence[str], None] = "6c1f8e2a4b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROPERTY_LOCATION_PROPERTY_INDEX = "ix_property_locations_property_id"
PROPERTY_LOCATION_PENDING_INDEX = (
    "uq_property_locations_one_pending_per_property"
)
PROPERTY_LOCATION_CURRENT_INDEX = (
    "uq_property_locations_one_current_per_property"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_property_locations_status",
        "property_locations",
        type_="check",
    )
    op.drop_index(
        PROPERTY_LOCATION_PROPERTY_INDEX,
        table_name="property_locations",
    )
    op.drop_constraint(
        "property_locations_property_id_fkey",
        "property_locations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "property_locations_property_id_fkey",
        "property_locations",
        "properties",
        ["property_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "property_locations",
        sa.Column("version_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "property_locations",
        sa.Column("submitted_by_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "property_locations",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "property_locations",
        sa.Column("is_current", sa.Boolean(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE property_locations "
            "SET version_number = 1, is_current = false"
        )
    )

    op.alter_column(
        "property_locations",
        "version_number",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("1"),
    )
    op.alter_column(
        "property_locations",
        "is_current",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )

    op.create_foreign_key(
        "property_locations_submitted_by_id_fkey",
        "property_locations",
        "users",
        ["submitted_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_property_locations_submitted_by_id",
        "property_locations",
        ["submitted_by_id"],
        unique=False,
    )
    op.create_index(
        PROPERTY_LOCATION_PROPERTY_INDEX,
        "property_locations",
        ["property_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_property_locations_property_version",
        "property_locations",
        ["property_id", "version_number"],
    )
    op.create_check_constraint(
        "ck_property_locations_version_number_positive",
        "property_locations",
        "version_number > 0",
    )
    op.create_check_constraint(
        "ck_property_locations_status",
        "property_locations",
        "status IN ('unverified', 'pending', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        "ck_property_locations_current_requires_approval",
        "property_locations",
        "NOT is_current OR status = 'approved'",
    )
    op.create_index(
        PROPERTY_LOCATION_PENDING_INDEX,
        "property_locations",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        PROPERTY_LOCATION_CURRENT_INDEX,
        "property_locations",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text("is_current IS TRUE"),
    )

    op.create_table(
        "property_location_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("verified_by", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("verification_method", sa.String(length=100), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_property_location_verifications_decision",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["property_locations.id"],
            name="property_location_verifications_location_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"],
            ["users.id"],
            name="property_location_verifications_verified_by_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "location_id",
            name="uq_property_location_verifications_location",
        ),
    )
    op.create_index(
        "ix_property_location_verifications_verified_by",
        "property_location_verifications",
        ["verified_by"],
        unique=False,
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Cannot generate an offline downgrade for versioned property "
            "locations because the location history safety check requires "
            "a live database."
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "LOCK TABLE property_locations, property_location_verifications "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    has_location_history = connection.scalar(
        sa.text(
            "SELECT "
            "EXISTS (SELECT 1 FROM property_location_verifications) "
            "OR EXISTS ("
            "  SELECT property_id FROM property_locations "
            "  GROUP BY property_id HAVING COUNT(*) > 1"
            ") "
            "OR EXISTS ("
            "  SELECT 1 FROM property_locations "
            "  WHERE status <> 'unverified' "
            "     OR version_number <> 1 "
            "     OR submitted_by_id IS NOT NULL "
            "     OR submitted_at IS NOT NULL "
            "     OR is_current IS TRUE"
            ")"
        )
    )
    if has_location_history:
        raise RuntimeError(
            "Cannot downgrade versioned property locations: location "
            "versions, verification decisions, or new location state would "
            "be lost."
        )

    op.drop_index(
        "ix_property_location_verifications_verified_by",
        table_name="property_location_verifications",
    )
    op.drop_table("property_location_verifications")

    op.drop_index(
        PROPERTY_LOCATION_PENDING_INDEX,
        table_name="property_locations",
    )
    op.drop_index(
        PROPERTY_LOCATION_CURRENT_INDEX,
        table_name="property_locations",
    )
    op.drop_constraint(
        "uq_property_locations_property_version",
        "property_locations",
        type_="unique",
    )
    op.drop_constraint(
        "ck_property_locations_version_number_positive",
        "property_locations",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_locations_current_requires_approval",
        "property_locations",
        type_="check",
    )
    op.drop_constraint(
        "ck_property_locations_status",
        "property_locations",
        type_="check",
    )
    op.drop_index(
        PROPERTY_LOCATION_PROPERTY_INDEX,
        table_name="property_locations",
    )
    op.drop_index(
        "ix_property_locations_submitted_by_id",
        table_name="property_locations",
    )
    op.drop_constraint(
        "property_locations_submitted_by_id_fkey",
        "property_locations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "property_locations_property_id_fkey",
        "property_locations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "property_locations_property_id_fkey",
        "property_locations",
        "properties",
        ["property_id"],
        ["id"],
    )

    op.drop_column("property_locations", "is_current")
    op.drop_column("property_locations", "submitted_at")
    op.drop_column("property_locations", "submitted_by_id")
    op.drop_column("property_locations", "version_number")

    op.create_check_constraint(
        "ck_property_locations_status",
        "property_locations",
        "status IN ('unverified')",
    )
    op.create_index(
        PROPERTY_LOCATION_PROPERTY_INDEX,
        "property_locations",
        ["property_id"],
        unique=True,
    )
