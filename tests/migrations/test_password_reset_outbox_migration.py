"""Opt-in PostgreSQL/PostGIS migration test for password-reset outbox support."""

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

PARENT_REVISION = "f4b2c8d91a63"
TARGET_REVISION = "b7e2c91a5f40"

TEST_DATABASE_NAME = "nestify_migration_test"
DENIED_DATABASE_NAMES = {"nestify", "nestify_pytest"}
POSTGIS_IMAGE = "postgis/postgis:16-3.4"

MIGRATION_TESTS_ENABLED = os.environ.get("RUN_MIGRATION_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not MIGRATION_TESTS_ENABLED,
    reason="requires RUN_MIGRATION_TESTS=1 and Docker/PostGIS",
)

USER_ID = UUID("a1b2c3d4-1000-4000-8000-000000000101")
INVITATION_ID = UUID("a1b2c3d4-2000-4000-8000-000000000101")
LEGACY_OUTBOX_ID = UUID("a1b2c3d4-3000-4000-8000-000000000101")
RESET_OUTBOX_ID = UUID("a1b2c3d4-3000-4000-8000-000000000102")
RESET_TOKEN_ID = UUID("a1b2c3d4-4000-4000-8000-000000000101")
INVALID_INVITATION_ID = UUID("a1b2c3d4-2000-4000-8000-000000000199")


@pytest.fixture(scope="module")
def migration_container():
    if not MIGRATION_TESTS_ENABLED:
        pytest.skip("requires RUN_MIGRATION_TESTS=1 and Docker/PostGIS")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        image=POSTGIS_IMAGE,
        username="nestify_migration",
        password="migration_test_password",
        dbname=TEST_DATABASE_NAME,
    ) as container:
        yield container


def _container_url(container) -> URL:
    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(5432))

    url = URL.create(
        drivername="postgresql+psycopg",
        username="nestify_migration",
        password="migration_test_password",
        host=host,
        port=port,
        database=TEST_DATABASE_NAME,
    )

    if url.database in DENIED_DATABASE_NAMES:
        pytest.fail(f"Refusing protected database {url.database!r}")

    if url.database != TEST_DATABASE_NAME:
        pytest.fail("Unexpected migration database name")

    if container.dbname != TEST_DATABASE_NAME:
        pytest.fail("Container is not configured for the migration test database")

    if url.host != host or url.port != port:
        pytest.fail("Database URL does not match the disposable container")

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


def _seed_legacy_data(connection, now: datetime) -> None:
    connection.execute(
        text(
            """
            INSERT INTO users
                (id, email, password_hash, role, is_active,
                 created_at, updated_at)
            VALUES
                (:id, 'migration-reset@example.invalid',
                 'not-a-real-password-hash', 'admin', true, :now, :now)
            """
        ),
        {"id": USER_ID, "now": now},
    )

    connection.execute(
        text(
            """
            INSERT INTO employee_invitations
                (id, email, token_hash, employee_number, department,
                 position, clearances, invited_by_user_id, expires_at,
                 redeemed_at, created_at)
            VALUES
                (:id, 'migration-invite@example.invalid',
                 :token_hash, 'MIGRATION-001', 'Operations',
                 'Test Officer', CAST(:clearances AS json), :invited_by,
                 :expires_at, NULL, :now)
            """
        ),
        {
            "id": INVITATION_ID,
            "token_hash": "a" * 64,
            "clearances": '["plate_operations"]',
            "invited_by": USER_ID,
            "expires_at": now.replace(year=now.year + 1),
            "now": now,
        },
    )

    connection.execute(
        text(
            """
            INSERT INTO email_outbox
                (id, employee_invitation_id, event_type,
                 encrypted_payload, encryption_key_version, status,
                 attempt_count, next_attempt_at, created_at)
            VALUES
                (:id, :invitation_id, 'employee_invitation',
                 'legacy-encrypted-payload', 'v1', 'pending',
                 0, :now, :now)
            """
        ),
        {
            "id": LEGACY_OUTBOX_ID,
            "invitation_id": INVITATION_ID,
            "now": now,
        },
    )


def test_password_reset_outbox_migration_upgrade_and_downgrade(
    migration_container,
):
    url = _container_url(migration_container)
    engine = create_engine(url, poolclass=NullPool)
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)

    try:
        # Establish database identity and PostGIS before the migration chain.
        with engine.begin() as connection:
            identity = connection.scalar(text("SELECT current_database()"))
            assert identity == TEST_DATABASE_NAME
            assert identity not in DENIED_DATABASE_NAMES

            connection.execute(
                text("CREATE EXTENSION IF NOT EXISTS postgis")
            )
            assert connection.scalar(
                text("SELECT PostGIS_Full_Version()")
            )

        parent_upgrade = _run_alembic(url, "upgrade", PARENT_REVISION)
        _assert_alembic_success(
            parent_upgrade, "upgrade", PARENT_REVISION
        )

        with engine.begin() as connection:
            assert _current_revision(connection) == PARENT_REVISION
            _seed_legacy_data(connection, now)

        target_upgrade = _run_alembic(url, "upgrade", TARGET_REVISION)
        _assert_alembic_success(
            target_upgrade, "upgrade", TARGET_REVISION
        )

        with engine.begin() as connection:
            assert _current_revision(connection) == TARGET_REVISION

            # Existing invitation-linked outbox data must be preserved.
            legacy = connection.execute(
                text(
                    """
                    SELECT employee_invitation_id, event_type,
                           encrypted_payload, encryption_key_version
                    FROM email_outbox
                    WHERE id = :id
                    """
                ),
                {"id": LEGACY_OUTBOX_ID},
            ).mappings().one()

            assert dict(legacy) == {
                "employee_invitation_id": INVITATION_ID,
                "event_type": "employee_invitation",
                "encrypted_payload": "legacy-encrypted-payload",
                "encryption_key_version": "v1",
            }

            # The invitation relationship must now be optional.
            nullable = connection.scalar(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'email_outbox'
                      AND column_name = 'employee_invitation_id'
                    """
                )
            )
            assert nullable == "YES"

            # The old FK and index must be removed.
            constraints = set(
                connection.scalars(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'email_outbox'::regclass
                        """
                    )
                )
            )
            assert (
                "email_outbox_employee_invitation_id_fkey"
                not in constraints
            )

            indexes = set(
                connection.scalars(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND tablename = 'email_outbox'
                        """
                    )
                )
            )
            assert (
                "ix_email_outbox_employee_invitation_id"
                not in indexes
            )

            # A password-reset outbox event can have no invitation ID.
            connection.execute(
                text(
                    """
                    INSERT INTO email_outbox
                        (id, employee_invitation_id, event_type,
                         encrypted_payload, encryption_key_version,
                         status, attempt_count, next_attempt_at, created_at)
                    VALUES
                        (:id, NULL, 'password_reset',
                         'encrypted-reset-payload', 'v1', 'pending',
                         0, :now, :now)
                    """
                ),
                {"id": RESET_OUTBOX_ID, "now": now},
            )

            # Password reset tokens must accept a valid user reference.
            connection.execute(
                text(
                    """
                    INSERT INTO password_reset_tokens
                        (id, user_id, token_hash, expires_at,
                         consumed_at, created_at)
                    VALUES
                        (:id, :user_id, :token_hash, :expires_at,
                         NULL, :now)
                    """
                ),
                {
                    "id": RESET_TOKEN_ID,
                    "user_id": USER_ID,
                    "token_hash": "b" * 64,
                    "expires_at": now.replace(minute=30),
                    "now": now,
                },
            )

            # Token hashes must be unique.
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            INSERT INTO password_reset_tokens
                                (id, user_id, token_hash, expires_at,
                                 consumed_at, created_at)
                            VALUES
                                (:id, :user_id, :token_hash, :expires_at,
                                 NULL, :now)
                            """
                        ),
                        {
                            "id": UUID(
                                "a1b2c3d4-4000-4000-8000-000000000102"
                            ),
                            "user_id": USER_ID,
                            "token_hash": "b" * 64,
                            "expires_at": now.replace(minute=30),
                            "now": now,
                        },
                    )

            assert connection.scalar(
                text("SELECT count(*) FROM password_reset_tokens")
            ) == 1

        # Downgrade must refuse to discard outbox rows without an invitation.
        null_outbox_downgrade = _run_alembic(
            url, "downgrade", PARENT_REVISION
        )
        assert null_outbox_downgrade.returncode != 0
        assert (
            "Cannot downgrade: email_outbox contains rows without "
            "employee_invitation_id."
            in null_outbox_downgrade.stdout
            + null_outbox_downgrade.stderr
        )

        with engine.begin() as connection:
            assert _current_revision(connection) == TARGET_REVISION
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM email_outbox "
                    "WHERE id = :id AND employee_invitation_id IS NULL"
                ),
                {"id": RESET_OUTBOX_ID},
            ) == 1

            # Remove the reset outbox row to reach the next downgrade guard.
            connection.execute(
                text("DELETE FROM email_outbox WHERE id = :id"),
                {"id": RESET_OUTBOX_ID},
            )

        # Downgrade must also refuse to discard password-reset token records.
        token_downgrade = _run_alembic(
            url, "downgrade", PARENT_REVISION
        )
        assert token_downgrade.returncode != 0
        assert (
            "Cannot downgrade: password_reset_tokens contains records."
            in token_downgrade.stdout + token_downgrade.stderr
        )

        with engine.begin() as connection:
            assert _current_revision(connection) == TARGET_REVISION

            connection.execute(
                text("DELETE FROM password_reset_tokens WHERE id = :id"),
                {"id": RESET_TOKEN_ID},
            )

        # With incompatible data removed, downgrade must restore the old schema.
        downgrade = _run_alembic(url, "downgrade", PARENT_REVISION)
        _assert_alembic_success(
            downgrade, "downgrade", PARENT_REVISION
        )

        with engine.begin() as connection:
            assert _current_revision(connection) == PARENT_REVISION

            nullable = connection.scalar(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'email_outbox'
                      AND column_name = 'employee_invitation_id'
                    """
                )
            )
            assert nullable == "NO"

            constraints = set(
                connection.scalars(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'email_outbox'::regclass
                        """
                    )
                )
            )
            assert (
                "email_outbox_employee_invitation_id_fkey"
                in constraints
            )

            indexes = set(
                connection.scalars(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND tablename = 'email_outbox'
                        """
                    )
                )
            )
            assert (
                "ix_email_outbox_employee_invitation_id" in indexes
            )

            assert connection.scalar(
                text(
                    "SELECT to_regclass('public.password_reset_tokens')"
                )
            ) is None

            # The original invitation-linked outbox record must still exist.
            assert connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM email_outbox
                    WHERE id = :id
                      AND employee_invitation_id = :invitation_id
                      AND encrypted_payload = 'legacy-encrypted-payload'
                    """
                ),
                {
                    "id": LEGACY_OUTBOX_ID,
                    "invitation_id": INVITATION_ID,
                },
            ) == 1

            # The restored FK must reject nonexistent invitation IDs.
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            INSERT INTO email_outbox
                                (id, employee_invitation_id, event_type,
                                 encrypted_payload, encryption_key_version,
                                 status, attempt_count, next_attempt_at,
                                 created_at)
                            VALUES
                                (:id, :invitation_id, 'employee_invitation',
                                 'invalid-reference', 'v1', 'pending',
                                 0, :now, :now)
                            """
                        ),
                        {
                            "id": UUID(
                                "a1b2c3d4-3000-4000-8000-000000000199"
                            ),
                            "invitation_id": INVALID_INVITATION_ID,
                            "now": now,
                        },
                    )

    finally:
        engine.dispose()
