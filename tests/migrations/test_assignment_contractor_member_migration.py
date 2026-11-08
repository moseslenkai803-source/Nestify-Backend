"""Real PostgreSQL tests for contractor/member assignment consistency migration."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "alembic.ini"

PARENT_REVISION = "4a7c9e2d1f60"
TARGET_REVISION = "9e3f6c2a1b74"

TEST_DATABASE_NAME = "nestify_migration_test"
DENIED_DATABASE_NAMES = {"nestify", "nestify_pytest"}
POSTGRES_IMAGE = "postgis/postgis:16-3.4"

MIGRATION_TESTS_ENABLED = os.environ.get("RUN_MIGRATION_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not MIGRATION_TESTS_ENABLED,
    reason="requires RUN_MIGRATION_TESTS=1 and Docker/PostGIS",
)

USER_A = UUID("a1b2c3d4-1000-4000-8000-000000000001")
USER_B = UUID("a1b2c3d4-1000-4000-8000-000000000002")
LANDLORD_ID = UUID("a1b2c3d4-1000-4000-8000-000000000003")
PROPERTY_ID = UUID("a1b2c3d4-1000-4000-8000-000000000004")
PLATE_ID = UUID("a1b2c3d4-1000-4000-8000-000000000005")

CONTRACTOR_A = UUID("a1b2c3d4-2000-4000-8000-000000000001")
CONTRACTOR_B = UUID("a1b2c3d4-2000-4000-8000-000000000002")

MEMBER_A = UUID("a1b2c3d4-3000-4000-8000-000000000001")
MEMBER_B = UUID("a1b2c3d4-3000-4000-8000-000000000002")

ASSIGNMENT_ID = UUID("a1b2c3d4-4000-4000-8000-000000000001")


@pytest.fixture(scope="module")
def migration_container():
    if not MIGRATION_TESTS_ENABLED:
        pytest.skip("requires RUN_MIGRATION_TESTS=1 and Docker/PostGIS")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        image=POSTGRES_IMAGE,
        username="nestify_migration",
        password="migration_test_password",
        dbname=TEST_DATABASE_NAME,
    ) as container:
        yield container


def _container_url(container) -> URL:
    url = URL.create(
        drivername="postgresql+psycopg",
        username="nestify_migration",
        password="migration_test_password",
        host=container.get_container_host_ip(),
        port=int(container.get_exposed_port(5432)),
        database=TEST_DATABASE_NAME,
    )

    if url.database in DENIED_DATABASE_NAMES:
        pytest.fail(f"Refusing protected database {url.database!r}")

    if url.database != TEST_DATABASE_NAME:
        pytest.fail(f"Unexpected database name: {url.database!r}")

    if container.dbname != TEST_DATABASE_NAME:
        pytest.fail("Container database name does not match test database")

    if (
        url.host != container.get_container_host_ip()
        or url.port != int(container.get_exposed_port(5432))
    ):
        pytest.fail("Database URL does not match disposable container")

    return url


def _run_alembic(
    url: URL,
    command: str,
    revision: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url.render_as_string(hide_password=False)

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            command,
            revision,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _assert_alembic_success(result, command: str, revision: str) -> None:
    assert result.returncode == 0, (
        f"Alembic {command} to {revision} failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _current_revision(connection) -> str:
    return connection.scalar(
        text("SELECT version_num FROM alembic_version")
    )


def _constraint_names(connection) -> set[str]:
    return set(
        connection.scalars(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE connamespace = 'public'::regnamespace"
            )
        )
    )


def _seed_rows(connection) -> None:
    now = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)

    connection.execute(
        text(
            """
            INSERT INTO users
                (id, email, password_hash, role, is_active,
                 created_at, updated_at)
            VALUES
                (:user_a, 'migration-a@example.invalid', 'not-a-real-hash',
                 'landlord', true, :now, :now),
                (:user_b, 'migration-b@example.invalid', 'not-a-real-hash',
                 'contractor', true, :now, :now)
            """
        ),
        {"user_a": USER_A, "user_b": USER_B, "now": now},
    )

    connection.execute(
        text(
            """
            INSERT INTO landlords
                (id, user_id, display_name, phone, landlord_type,
                 created_at, updated_at)
            VALUES
                (:id, :user_id, 'Migration Test Landlord',
                 '+254700000000', 'individual', :now, :now)
            """
        ),
        {"id": LANDLORD_ID, "user_id": USER_A, "now": now},
    )

    connection.execute(
        text(
            """
            INSERT INTO properties
                (id, landlord_id, property_code, name, property_type,
                 status, created_at, updated_at)
            VALUES
                (:id, :landlord_id, 'MIGRATION-ASSIGNMENT-001',
                 'Migration Test Property', 'residential',
                 'active', :now, :now)
            """
        ),
        {"id": PROPERTY_ID, "landlord_id": LANDLORD_ID, "now": now},
    )

    connection.execute(
        text(
            """
            INSERT INTO address_plates
                (id, manufacturing_order_id, property_id, plate_code,
                 status, activated_at, created_at, updated_at)
            VALUES
                (:id, NULL, :property_id, 'MIGRATION-ASSIGNMENT-PLATE',
                 'unactivated', NULL, :now, :now)
            """
        ),
        {"id": PLATE_ID, "property_id": PROPERTY_ID, "now": now},
    )

    connection.execute(
        text(
            """
            INSERT INTO contractors
                (id, name, contractor_type, status, created_at, updated_at)
            VALUES
                (:contractor_a, 'Contractor A', 'company', 'active', :now, :now),
                (:contractor_b, 'Contractor B', 'company', 'active', :now, :now)
            """
        ),
        {
            "contractor_a": CONTRACTOR_A,
            "contractor_b": CONTRACTOR_B,
            "now": now,
        },
    )

    connection.execute(
        text(
            """
            INSERT INTO contractor_members
                (id, contractor_id, user_id, is_active, created_at, updated_at)
            VALUES
                (:member_a, :contractor_a, :user_a, true, :now, :now),
                (:member_b, :contractor_b, :user_b, true, :now, :now)
            """
        ),
        {
            "member_a": MEMBER_A,
            "member_b": MEMBER_B,
            "contractor_a": CONTRACTOR_A,
            "contractor_b": CONTRACTOR_B,
            "user_a": USER_A,
            "user_b": USER_B,
            "now": now,
        },
    )

    # Deliberately invalid: the assignment says Contractor A, but its
    # contractor member belongs to Contractor B.
    connection.execute(
        text(
            """
            INSERT INTO installation_assignments
                (id, property_id, plate_id, contractor_id,
                 contractor_member_id, assigned_by, assigned_at,
                 due_at, status, created_at, updated_at)
            VALUES
                (:id, :property_id, :plate_id, :contractor_id,
                 :member_id, :assigned_by, :now,
                 NULL, 'assigned', :now, :now)
            """
        ),
        {
            "id": ASSIGNMENT_ID,
            "property_id": PROPERTY_ID,
            "plate_id": PLATE_ID,
            "contractor_id": CONTRACTOR_A,
            "member_id": MEMBER_B,
            "assigned_by": USER_A,
            "now": now,
        },
    )


def test_assignment_contractor_member_consistency_migration(
    migration_container,
):
    url = _container_url(migration_container)
    engine = create_engine(url, poolclass=NullPool)

    try:
        # Establish the exact schema immediately before the target migration.
        result = _run_alembic(url, "upgrade", PARENT_REVISION)
        _assert_alembic_success(result, "upgrade", PARENT_REVISION)

        with engine.begin() as connection:
            assert _current_revision(connection) == PARENT_REVISION
            _seed_rows(connection)

            before_constraints = _constraint_names(connection)
            assert (
                "installation_assignments_contractor_member_id_fkey"
                in before_constraints
            )
            assert (
                "fk_installation_assignments_member_contractor"
                not in before_constraints
            )
            assert (
                "uq_contractor_members_id_contractor_id"
                not in before_constraints
            )

        # Case 1: migration must reject existing mismatched data.
        result = _run_alembic(url, "upgrade", TARGET_REVISION)

        assert result.returncode != 0
        assert "mismatched installation assignment(s) found" in (
            result.stdout + result.stderr
        )

        with engine.connect() as connection:
            assert _current_revision(connection) == PARENT_REVISION

            after_failed_upgrade = _constraint_names(connection)
            assert (
                "installation_assignments_contractor_member_id_fkey"
                in after_failed_upgrade
            )
            assert (
                "fk_installation_assignments_member_contractor"
                not in after_failed_upgrade
            )
            assert (
                "uq_contractor_members_id_contractor_id"
                not in after_failed_upgrade
            )

            assert connection.scalar(
                text("SELECT count(*) FROM installation_assignments")
            ) == 1

        # Correct the legacy data so the migration can proceed.
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE installation_assignments
                    SET contractor_member_id = :member_id
                    WHERE id = :assignment_id
                    """
                ),
                {
                    "member_id": MEMBER_A,
                    "assignment_id": ASSIGNMENT_ID,
                },
            )

        # Case 2: valid existing data must allow the migration.
        result = _run_alembic(url, "upgrade", TARGET_REVISION)
        _assert_alembic_success(result, "upgrade", TARGET_REVISION)

        with engine.connect() as connection:
            assert _current_revision(connection) == TARGET_REVISION

            constraints = _constraint_names(connection)
            assert (
                "fk_installation_assignments_member_contractor"
                in constraints
            )
            assert (
                "uq_contractor_members_id_contractor_id"
                in constraints
            )
            assert (
                "installation_assignments_contractor_member_id_fkey"
                not in constraints
            )

            assignment = connection.execute(
                text(
                    """
                    SELECT contractor_id, contractor_member_id
                    FROM installation_assignments
                    WHERE id = :id
                    """
                ),
                {"id": ASSIGNMENT_ID},
            ).one()

            assert assignment.contractor_id == CONTRACTOR_A
            assert assignment.contractor_member_id == MEMBER_A

        # PostgreSQL must reject a contractor/member mismatch after upgrade.
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE installation_assignments
                        SET contractor_id = :wrong_contractor
                        WHERE id = :assignment_id
                        """
                    ),
                    {
                        "wrong_contractor": CONTRACTOR_B,
                        "assignment_id": ASSIGNMENT_ID,
                    },
                )

        # The failed statement must not have changed the valid assignment.
        with engine.connect() as connection:
            assignment = connection.execute(
                text(
                    """
                    SELECT contractor_id, contractor_member_id
                    FROM installation_assignments
                    WHERE id = :id
                    """
                ),
                {"id": ASSIGNMENT_ID},
            ).one()

            assert assignment.contractor_id == CONTRACTOR_A
            assert assignment.contractor_member_id == MEMBER_A

        # Case 3: downgrade must restore the original single-column FK.
        result = _run_alembic(url, "downgrade", PARENT_REVISION)
        _assert_alembic_success(result, "downgrade", PARENT_REVISION)

        with engine.connect() as connection:
            assert _current_revision(connection) == PARENT_REVISION

            downgraded_constraints = _constraint_names(connection)
            assert (
                "installation_assignments_contractor_member_id_fkey"
                in downgraded_constraints
            )
            assert (
                "fk_installation_assignments_member_contractor"
                not in downgraded_constraints
            )
            assert (
                "uq_contractor_members_id_contractor_id"
                not in downgraded_constraints
            )

            assert connection.scalar(
                text("SELECT count(*) FROM installation_assignments")
            ) == 1

    finally:
        engine.dispose()
