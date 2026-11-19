"""Real PostgreSQL tests for the platform settings migration."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "alembic.ini"

PARENT_REVISION = "d6a9f2c41b70"
TARGET_REVISION = "f4b2c8d91a63"

TEST_DATABASE_NAME = "nestify_migration_test"
DENIED_DATABASE_NAMES = {"nestify", "nestify_pytest"}
POSTGRES_IMAGE = "postgis/postgis:16-3.4"

MIGRATION_TESTS_ENABLED = os.environ.get("RUN_MIGRATION_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not MIGRATION_TESTS_ENABLED,
    reason="requires RUN_MIGRATION_TESTS=1 and Docker/PostGIS",
)

USER_A = UUID("a1b2c3d4-1000-4000-8000-000000000101")
USER_B = UUID("a1b2c3d4-1000-4000-8000-000000000102")
AUDIT_ID = UUID("a1b2c3d4-2000-4000-8000-000000000101")


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

    if url.database != TEST_DATABASE_NAME or container.dbname != TEST_DATABASE_NAME:
        pytest.fail("Unexpected migration test database name")

    if url.host != host or url.port != port:
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


def _seed_users(connection) -> None:
    now = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)

    connection.execute(
        text(
            """
            INSERT INTO users
                (id, email, password_hash, role, is_active,
                 created_at, updated_at)
            VALUES
                (:user_a, 'settings-a@example.invalid', 'not-a-real-hash',
                 'admin', true, :now, :now),
                (:user_b, 'settings-b@example.invalid', 'not-a-real-hash',
                 'admin', true, :now, :now)
            """
        ),
        {"user_a": USER_A, "user_b": USER_B, "now": now},
    )


def test_platform_settings_migration_upgrade_constraints_and_downgrade(
    migration_container,
):
    url = _container_url(migration_container)
    engine = create_engine(url, poolclass=NullPool)

    try:
        with engine.begin() as connection:
            identity = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            assert identity == TEST_DATABASE_NAME
            assert identity not in DENIED_DATABASE_NAMES

            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            assert connection.scalar(text("SELECT PostGIS_Full_Version()"))

        parent = _run_alembic(url, "upgrade", PARENT_REVISION)
        _assert_alembic_success(parent, "upgrade", PARENT_REVISION)

        with engine.begin() as connection:
            assert _current_revision(connection) == PARENT_REVISION
            _seed_users(connection)

        upgrade = _run_alembic(url, "upgrade", TARGET_REVISION)
        _assert_alembic_success(upgrade, "upgrade", TARGET_REVISION)

        with engine.begin() as connection:
            assert _current_revision(connection) == TARGET_REVISION

            settings = connection.execute(
                text(
                    """
                    SELECT id, organization_name, legal_name, support_email,
                           support_phone, timezone, locale, currency_code,
                           date_format, time_format, updated_by
                    FROM platform_settings
                    """
                )
            ).mappings().one()

            assert dict(settings) == {
                "id": 1,
                "organization_name": "Nestify",
                "legal_name": None,
                "support_email": None,
                "support_phone": None,
                "timezone": "Africa/Nairobi",
                "locale": "en-KE",
                "currency_code": "KES",
                "date_format": "DD/MM/YYYY",
                "time_format": "24h",
                "updated_by": None,
            }

            assert connection.scalar(
                text("SELECT count(*) FROM platform_settings")
            ) == 1

            assert connection.scalar(
                text("SELECT count(*) FROM platform_setting_audit_logs")
            ) == 0

            indexes = set(
                connection.scalars(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND tablename = 'platform_setting_audit_logs'
                        """
                    )
                )
            )
            assert {
                "ix_platform_setting_audit_logs_changed_at",
                "ix_platform_setting_audit_logs_setting_key",
                "ix_platform_setting_audit_logs_actor_user_id",
            }.issubset(indexes)

            # The singleton constraint must reject any other ID.
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text("UPDATE platform_settings SET id = 2 WHERE id = 1")
                    )

            # Currency must be uppercase and exactly three characters.
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE platform_settings "
                            "SET currency_code = 'kes' WHERE id = 1"
                        )
                    )

            # Date and time formats must be from the supported sets.
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE platform_settings "
                            "SET date_format = 'DD-MM-YYYY' WHERE id = 1"
                        )
                    )

            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE platform_settings "
                            "SET time_format = '18h' WHERE id = 1"
                        )
                    )

            # updated_by must become NULL when its user is deleted.
            connection.execute(
                text(
                    "UPDATE platform_settings SET updated_by = :user_id "
                    "WHERE id = 1"
                ),
                {"user_id": USER_B},
            )
            connection.execute(
                text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": USER_B},
            )

            assert connection.scalar(
                text("SELECT updated_by FROM platform_settings WHERE id = 1")
            ) is None

            # Audit history must prevent deletion of its actor.
            connection.execute(
                text(
                    """
                    INSERT INTO platform_setting_audit_logs
                        (id, actor_user_id, setting_key, previous_value,
                         new_value, reason, changed_at)
                    VALUES
                        (:id, :actor_id, 'organization_name',
                         'Nestify', 'Nestify Kenya', 'Migration test', :now)
                    """
                ),
                {
                    "id": AUDIT_ID,
                    "actor_id": USER_A,
                    "now": datetime.now(timezone.utc),
                },
            )

            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text("DELETE FROM users WHERE id = :user_id"),
                        {"user_id": USER_A},
                    )

            # Audit history must reject UPDATE, DELETE, and TRUNCATE.
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            UPDATE platform_setting_audit_logs
                            SET reason = 'Modified'
                            WHERE id = :id
                            """
                        ),
                        {"id": AUDIT_ID},
                    )

            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "DELETE FROM platform_setting_audit_logs "
                            "WHERE id = :id"
                        ),
                        {"id": AUDIT_ID},
                    )

            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        text("TRUNCATE TABLE platform_setting_audit_logs")
                    )

            assert connection.scalar(
                text("SELECT count(*) FROM platform_setting_audit_logs")
            ) == 1

        downgrade = _run_alembic(url, "downgrade", PARENT_REVISION)
        _assert_alembic_success(downgrade, "downgrade", PARENT_REVISION)

        with engine.connect() as connection:
            assert _current_revision(connection) == PARENT_REVISION

            assert connection.scalar(
                text("SELECT to_regclass('public.platform_settings')")
            ) is None

            assert connection.scalar(
                text("SELECT to_regclass('public.platform_setting_audit_logs')")
            ) is None

            # The parent schema must remain intact.
            assert connection.scalar(
                text("SELECT to_regclass('public.users')")
            ) is not None

    finally:
        engine.dispose()
