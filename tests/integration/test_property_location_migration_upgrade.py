"""Opt-in real PostgreSQL/PostGIS migration-upgrade integration test.

This test is excluded from ordinary collection because it requires Docker and
starts a disposable PostGIS container. Enable it explicitly with
RUN_MIGRATION_TESTS=1.
"""

from __future__ import annotations

import os
import re
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
PARENT_REVISION = "6c1f8e2a4b70"
TARGET_REVISION = "a94c2e7d61f0"
TEST_DATABASE_NAME = "nestify_migration_test"
DENIED_DATABASE_NAMES = {"nestify", "nestify_pytest"}
POSTGIS_IMAGE = "postgis/postgis:16-3.4"
MIGRATION_TESTS_ENABLED = os.environ.get("RUN_MIGRATION_TESTS") == "1"
pytestmark = pytest.mark.skipif(
    not MIGRATION_TESTS_ENABLED,
    reason="requires opt-in with RUN_MIGRATION_TESTS=1 and Docker/PostGIS",
)

FIXTURE_USER_ID = UUID("a1b2c3d4-1000-4000-8000-000000000001")
FIXTURE_LANDLORD_ID = UUID("a1b2c3d4-1000-4000-8000-000000000002")
FIXTURE_ROWS = (
    {
        "property_id": UUID("a1b2c3d4-1000-4000-8000-000000000011"),
        "location_id": UUID("a1b2c3d4-1000-4000-8000-000000000101"),
        "property_code": "MIGRATION-LEGACY-001",
        "latitude": -1.286389,
        "longitude": 36.817223,
        "source": "legacy_gps",
        "capture_method": "mobile_gnss",
        "accuracy_meters": 4.25,
        "captured_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "created_at": datetime(2026, 1, 2, 3, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 2, 3, 6, 0, tzinfo=timezone.utc),
    },
    {
        "property_id": UUID("a1b2c3d4-1000-4000-8000-000000000012"),
        "location_id": UUID("a1b2c3d4-1000-4000-8000-000000000102"),
        "property_code": "MIGRATION-LEGACY-002",
        "latitude": -4.043477,
        "longitude": 39.668206,
        "source": "legacy_survey",
        "capture_method": "field_survey",
        "accuracy_meters": None,
        "captured_at": datetime(2026, 2, 7, 8, 9, 10, tzinfo=timezone.utc),
        "created_at": datetime(2026, 2, 7, 8, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 2, 7, 8, 11, 0, tzinfo=timezone.utc),
    },
)

SNAPSHOT_COLUMNS = (
    "location_id",
    "property_id",
    "latitude",
    "longitude",
    "source",
    "capture_method",
    "accuracy_meters",
    "captured_at",
    "status",
    "created_at",
    "updated_at",
    "geometry_ewkb",
    "geometry_srid",
)


@pytest.fixture(scope="module")
def migration_container():
    if not MIGRATION_TESTS_ENABLED:
        pytest.skip(
            "requires opt-in with RUN_MIGRATION_TESTS=1 and Docker/PostGIS"
        )
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
    _assert_container_url_identity(url, container)
    return url


def _assert_container_url_identity(url: URL, container) -> None:
    if url.database in DENIED_DATABASE_NAMES:
        pytest.fail(f"Refusing protected database target {url.database!r}")
    if url.database != TEST_DATABASE_NAME:
        pytest.fail(
            f"Unexpected migration database {url.database!r}; "
            f"expected {TEST_DATABASE_NAME!r}"
        )
    if container.dbname != TEST_DATABASE_NAME:
        pytest.fail("Disposable container is not configured for the test database")
    if (
        url.host != container.get_container_host_ip()
        or url.port != int(container.get_exposed_port(5432))
    ):
        pytest.fail("Migration URL does not match the owned container endpoint")


def _run_alembic(url: URL, revision: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url.render_as_string(hide_password=False)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            "upgrade",
            revision,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _assert_alembic_succeeded(
    result: subprocess.CompletedProcess[str],
    revision: str,
) -> None:
    assert result.returncode == 0, (
        f"Alembic upgrade to {revision} failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _seed_legacy_rows(connection) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    connection.execute(
        text(
            "INSERT INTO users "
            "(id, email, password_hash, role, is_active, created_at, updated_at) "
            "VALUES (:id, :email, :password_hash, :role, true, :created_at, "
            ":updated_at)"
        ),
        {
            "id": FIXTURE_USER_ID,
            "email": "migration-test-owner@example.invalid",
            "password_hash": "not-a-real-password-hash",
            "role": "landlord",
            "created_at": now,
            "updated_at": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO landlords "
            "(id, user_id, display_name, phone, landlord_type, created_at, "
            "updated_at) VALUES (:id, :user_id, :display_name, :phone, "
            ":landlord_type, :created_at, :updated_at)"
        ),
        {
            "id": FIXTURE_LANDLORD_ID,
            "user_id": FIXTURE_USER_ID,
            "display_name": "Migration Test Owner",
            "phone": "+254700000000",
            "landlord_type": "individual",
            "created_at": now,
            "updated_at": now,
        },
    )

    for row in FIXTURE_ROWS:
        connection.execute(
            text(
                "INSERT INTO properties "
                "(id, landlord_id, property_code, name, property_type, status, "
                "created_at, updated_at) VALUES "
                "(:id, :landlord_id, :property_code, :name, :property_type, "
                ":status, :created_at, :updated_at)"
            ),
            {
                "id": row["property_id"],
                "landlord_id": FIXTURE_LANDLORD_ID,
                "property_code": row["property_code"],
                "name": f"Migration Test {row['property_code']}",
                "property_type": "residential",
                "status": "active",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
        connection.execute(
            text(
                "INSERT INTO property_locations "
                "(id, property_id, latitude, longitude, location, source, "
                "capture_method, accuracy_meters, captured_at, status, "
                "created_at, updated_at) VALUES "
                "(:id, :property_id, :latitude, :longitude, "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326), "
                ":source, :capture_method, :accuracy_meters, :captured_at, "
                "'unverified', :created_at, :updated_at)"
            ),
            {
                "id": row["location_id"],
                "property_id": row["property_id"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "source": row["source"],
                "capture_method": row["capture_method"],
                "accuracy_meters": row["accuracy_meters"],
                "captured_at": row["captured_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )


def _location_snapshot(connection) -> dict[UUID, dict]:
    result = connection.execute(
        text(
            "SELECT id AS location_id, property_id, latitude, longitude, "
            "source, capture_method, accuracy_meters, captured_at, status, "
            "created_at, updated_at, ST_AsEWKB(location) AS geometry_ewkb, "
            "ST_SRID(location) AS geometry_srid "
            "FROM property_locations ORDER BY id"
        )
    ).mappings()
    return {
        row["location_id"]: {column: row[column] for column in SNAPSHOT_COLUMNS}
        for row in result
    }


def _property_snapshot(connection) -> dict[UUID, dict]:
    result = connection.execute(
        text(
            "SELECT id, landlord_id, property_code, name, property_type, "
            "status, created_at, updated_at FROM properties ORDER BY id"
        )
    ).mappings()
    return {row["id"]: dict(row) for row in result}


def _assert_legacy_data_preserved(connection, before: dict[UUID, dict]) -> None:
    after = _location_snapshot(connection)
    assert set(after) == set(before) == {
        row["location_id"] for row in FIXTURE_ROWS
    }
    assert {row["property_id"] for row in after.values()} == {
        row["property_id"] for row in before.values()
    }

    for location_id, expected in before.items():
        actual = after[location_id]
        assert actual == expected

    versioned_rows = connection.execute(
        text(
            "SELECT id, version_number, is_current, submitted_by_id, submitted_at "
            "FROM property_locations"
        )
    ).mappings()
    assert {
        row["id"]: (
            row["version_number"],
            row["is_current"],
            row["submitted_by_id"],
            row["submitted_at"],
        )
        for row in versioned_rows
    } == {
        location_id: (1, False, None, None) for location_id in before
    }
    assert connection.scalar(
        text("SELECT count(*) FROM property_location_verifications")
    ) == 0


def _assert_properties_preserved(connection, before: dict[UUID, dict]) -> None:
    after = _property_snapshot(connection)
    assert set(after) == set(before) == {
        row["property_id"] for row in FIXTURE_ROWS
    }
    assert after == before


def _catalog_constraints(connection) -> dict[str, dict]:
    rows = connection.execute(
        text(
            "SELECT con.conname, con.contype, con.confdeltype, "
            "pg_get_constraintdef(con.oid) AS definition "
            "FROM pg_constraint AS con "
            "JOIN pg_class AS rel ON rel.oid = con.conrelid "
            "JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace "
            "WHERE ns.nspname = 'public' "
            "AND rel.relname IN "
            "('property_locations', 'property_location_verifications')"
        )
    ).mappings()
    return {row["conname"]: dict(row) for row in rows}


def _catalog_indexes(connection) -> dict[str, dict]:
    rows = connection.execute(
        text(
            "SELECT index_relation.relname AS indexname, "
            "table_relation.relname AS tablename, "
            "index_data.indisunique AS is_unique, "
            "index_data.indnkeyatts AS key_count, "
            "pg_get_indexdef(index_data.indexrelid, 1, true) AS key_column, "
            "pg_get_expr(index_data.indpred, index_data.indrelid) AS predicate, "
            "access_method.amname AS access_method "
            "FROM pg_index AS index_data "
            "JOIN pg_class AS index_relation "
            "ON index_relation.oid = index_data.indexrelid "
            "JOIN pg_class AS table_relation "
            "ON table_relation.oid = index_data.indrelid "
            "JOIN pg_namespace AS table_namespace "
            "ON table_namespace.oid = table_relation.relnamespace "
            "JOIN pg_am AS access_method "
            "ON access_method.oid = index_relation.relam "
            "WHERE table_namespace.nspname = 'public' "
            "AND table_relation.relname IN "
            "('property_locations', 'property_location_verifications')"
        )
    ).all()
    return {
        row.indexname: {
            "tablename": row.tablename,
            "is_unique": row.is_unique,
            "key_count": row.key_count,
            "key_column": row.key_column,
            "predicate": row.predicate,
            "access_method": row.access_method,
        }
        for row in rows
    }


def _normalize_index_predicate(predicate: str) -> str:
    without_type_casts = re.sub(
        r"::\s*(?:character varying|varchar|text|boolean)",
        "",
        predicate,
        flags=re.IGNORECASE,
    )
    return re.sub(r"[\s()]", "", without_type_casts).lower()


def _assert_schema_objects(connection) -> None:
    assert connection.scalar(
        text("SELECT to_regclass('public.property_location_verifications')")
    ) == "property_location_verifications"

    constraints = _catalog_constraints(connection)
    expected_constraint_types = {
        "property_locations_pkey": "p",
        "property_locations_property_id_fkey": "f",
        "property_locations_submitted_by_id_fkey": "f",
        "uq_property_locations_property_version": "u",
        "ck_property_locations_version_number_positive": "c",
        "ck_property_locations_status": "c",
        "ck_property_locations_current_requires_approval": "c",
        "property_location_verifications_pkey": "p",
        "property_location_verifications_location_id_fkey": "f",
        "property_location_verifications_verified_by_fkey": "f",
        "uq_property_location_verifications_location": "u",
        "ck_property_location_verifications_decision": "c",
    }
    for name, constraint_type in expected_constraint_types.items():
        assert constraints[name]["contype"] == constraint_type

    for name in (
        "property_locations_property_id_fkey",
        "property_locations_submitted_by_id_fkey",
        "property_location_verifications_location_id_fkey",
        "property_location_verifications_verified_by_fkey",
    ):
        assert constraints[name]["confdeltype"] == "r"

    expected_foreign_keys = {
        "property_locations_property_id_fkey": "properties(id)",
        "property_locations_submitted_by_id_fkey": "users(id)",
        "property_location_verifications_location_id_fkey": (
            "property_locations(id)"
        ),
        "property_location_verifications_verified_by_fkey": "users(id)",
    }
    for name, referenced_table in expected_foreign_keys.items():
        definition = constraints[name]["definition"]
        assert "FOREIGN KEY" in definition
        assert f"REFERENCES {referenced_table}" in definition
        assert "ON DELETE RESTRICT" in definition

    location_status_definition = constraints[
        "ck_property_locations_status"
    ]["definition"]
    for status in ("unverified", "pending", "approved", "rejected"):
        assert status in location_status_definition
    assert "version_number > 0" in constraints[
        "ck_property_locations_version_number_positive"
    ]["definition"]
    assert "NOT is_current" in constraints[
        "ck_property_locations_current_requires_approval"
    ]["definition"]
    current_check = constraints[
        "ck_property_locations_current_requires_approval"
    ]["definition"]
    assert "is_current" in current_check
    assert "approved" in current_check
    assert "approved" in constraints[
        "ck_property_location_verifications_decision"
    ]["definition"]
    assert "rejected" in constraints[
        "ck_property_location_verifications_decision"
    ]["definition"]

    indexes = _catalog_indexes(connection)
    expected_indexes = {
        "ix_property_locations_property_id",
        "ix_property_locations_submitted_by_id",
        "idx_property_locations_location",
        "uq_property_locations_one_pending_per_property",
        "uq_property_locations_one_current_per_property",
        "ix_property_location_verifications_verified_by",
    }
    assert expected_indexes <= indexes.keys()
    assert indexes["idx_property_locations_location"]["access_method"] == "gist"
    assert indexes["idx_property_locations_location"]["key_column"] == "location"

    pending_index = indexes["uq_property_locations_one_pending_per_property"]
    assert pending_index["tablename"] == "property_locations"
    assert pending_index["is_unique"] is True
    assert pending_index["key_count"] == 1
    assert pending_index["key_column"] == "property_id"
    assert pending_index["predicate"] is not None
    assert _normalize_index_predicate(pending_index["predicate"]) == (
        "status='pending'"
    )

    current_index = indexes["uq_property_locations_one_current_per_property"]
    assert current_index["tablename"] == "property_locations"
    assert current_index["is_unique"] is True
    assert current_index["key_count"] == 1
    assert current_index["key_column"] == "property_id"
    assert current_index["predicate"] is not None
    assert _normalize_index_predicate(current_index["predicate"]) == (
        "is_currentistrue"
    )

    verification_columns = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = 'property_location_verifications'"
            )
        )
    }
    assert verification_columns == {
        "id",
        "location_id",
        "verified_by",
        "decision",
        "verification_method",
        "verified_at",
        "notes",
        "created_at",
    }


def _assert_constraints_enforced(connection) -> None:
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                text(
                    "UPDATE property_locations SET version_number = 0 "
                    "WHERE id = :id"
                ),
                {"id": FIXTURE_ROWS[0]["location_id"]},
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO property_locations "
                    "(id, property_id, version_number, latitude, longitude, "
                    "location, source, capture_method, captured_at, status, "
                    "is_current, created_at, updated_at) "
                    "VALUES (:id, :property_id, 1, 0, 0, "
                    "ST_SetSRID(ST_MakePoint(0, 0), 4326), 'test', 'test', "
                    ":captured_at, 'unverified', false, :created_at, "
                    ":updated_at)"
                ),
                {
                    "id": UUID("a1b2c3d4-2000-4000-8000-000000000001"),
                    "property_id": FIXTURE_ROWS[0]["property_id"],
                    "captured_at": FIXTURE_ROWS[0]["captured_at"],
                    "created_at": FIXTURE_ROWS[0]["created_at"],
                    "updated_at": FIXTURE_ROWS[0]["updated_at"],
                },
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                text(
                    "UPDATE property_locations SET is_current = true "
                    "WHERE id = :id"
                ),
                {"id": FIXTURE_ROWS[0]["location_id"]},
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                text(
                    "UPDATE property_locations SET status = 'not-a-status' "
                    "WHERE id = :id"
                ),
                {"id": FIXTURE_ROWS[0]["location_id"]},
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            for version_number, identifier in (
                (2, "a1b2c3d4-2000-4000-8000-000000000002"),
                (3, "a1b2c3d4-2000-4000-8000-000000000003"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO property_locations "
                        "(id, property_id, version_number, latitude, longitude, "
                        "location, source, capture_method, captured_at, status, "
                        "is_current, created_at, updated_at) "
                        "VALUES (:id, :property_id, :version_number, 0, 0, "
                        "ST_SetSRID(ST_MakePoint(0, 0), 4326), 'test', 'test', "
                        ":captured_at, 'pending', false, :created_at, "
                        ":updated_at)"
                    ),
                    {
                        "id": UUID(identifier),
                        "property_id": FIXTURE_ROWS[0]["property_id"],
                        "version_number": version_number,
                        "captured_at": FIXTURE_ROWS[0]["captured_at"],
                        "created_at": FIXTURE_ROWS[0]["created_at"],
                        "updated_at": FIXTURE_ROWS[0]["updated_at"],
                    },
                )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            for version_number, identifier in (
                (4, "a1b2c3d4-2000-4000-8000-000000000004"),
                (5, "a1b2c3d4-2000-4000-8000-000000000005"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO property_locations "
                        "(id, property_id, version_number, latitude, longitude, "
                        "location, source, capture_method, captured_at, status, "
                        "is_current, created_at, updated_at) "
                        "VALUES (:id, :property_id, :version_number, 0, 0, "
                        "ST_SetSRID(ST_MakePoint(0, 0), 4326), 'test', 'test', "
                        ":captured_at, 'approved', true, :created_at, "
                        ":updated_at)"
                    ),
                    {
                        "id": UUID(identifier),
                        "property_id": FIXTURE_ROWS[0]["property_id"],
                        "version_number": version_number,
                        "captured_at": FIXTURE_ROWS[0]["captured_at"],
                        "created_at": FIXTURE_ROWS[0]["created_at"],
                        "updated_at": FIXTURE_ROWS[0]["updated_at"],
                    },
                )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO property_location_verifications "
                    "(id, location_id, verified_by, decision, "
                    "verification_method, verified_at, created_at) "
                    "VALUES (:id, :location_id, :verified_by, 'invalid', "
                    "'test', :verified_at, :created_at)"
                ),
                {
                    "id": UUID("a1b2c3d4-2000-4000-8000-000000000201"),
                    "location_id": FIXTURE_ROWS[0]["location_id"],
                    "verified_by": FIXTURE_USER_ID,
                    "verified_at": FIXTURE_ROWS[0]["captured_at"],
                    "created_at": FIXTURE_ROWS[0]["created_at"],
                },
            )


def test_property_location_migration_upgrade_preserves_legacy_data(
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

        parent_upgrade = _run_alembic(url, PARENT_REVISION)
        _assert_alembic_succeeded(parent_upgrade, PARENT_REVISION)

        with engine.begin() as connection:
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == PARENT_REVISION
            _seed_legacy_rows(connection)

        with engine.connect() as connection:
            before = _location_snapshot(connection)
            properties_before = _property_snapshot(connection)
        assert len(before) == len(FIXTURE_ROWS)
        assert len(properties_before) == len(FIXTURE_ROWS)
        assert {row["geometry_srid"] for row in before.values()} == {4326}

        target_upgrade = _run_alembic(url, TARGET_REVISION)
        _assert_alembic_succeeded(target_upgrade, TARGET_REVISION)

        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT current_database()")
            ) == TEST_DATABASE_NAME
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == TARGET_REVISION
            _assert_legacy_data_preserved(connection, before)
            _assert_properties_preserved(connection, properties_before)
            _assert_schema_objects(connection)
            _assert_constraints_enforced(connection)
            assert connection.scalar(
                text("SELECT count(*) FROM property_location_verifications")
            ) == 0
    finally:
        engine.dispose()
