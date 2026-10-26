"""enforce assignment contractor/member consistency

Revision ID: 9e3f6c2a1b74
Revises: 4a7c9e2d1f60
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9e3f6c2a1b74"
down_revision: Union[str, Sequence[str], None] = "4a7c9e2d1f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    mismatch_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM installation_assignments AS ia
            JOIN contractor_members AS cm
              ON cm.id = ia.contractor_member_id
            WHERE ia.contractor_id <> cm.contractor_id
            """
        )
    ).scalar_one()

    if mismatch_count:
        raise RuntimeError(
            "Cannot enforce contractor/member consistency: "
            f"{mismatch_count} mismatched installation assignment(s) found."
        )

    op.create_unique_constraint(
        "uq_contractor_members_id_contractor_id",
        "contractor_members",
        ["id", "contractor_id"],
    )

    op.drop_constraint(
        "installation_assignments_contractor_member_id_fkey",
        "installation_assignments",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_installation_assignments_member_contractor",
        "installation_assignments",
        "contractor_members",
        ["contractor_member_id", "contractor_id"],
        ["id", "contractor_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_installation_assignments_member_contractor",
        "installation_assignments",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "installation_assignments_contractor_member_id_fkey",
        "installation_assignments",
        "contractor_members",
        ["contractor_member_id"],
        ["id"],
    )

    op.drop_constraint(
        "uq_contractor_members_id_contractor_id",
        "contractor_members",
        type_="unique",
    )
