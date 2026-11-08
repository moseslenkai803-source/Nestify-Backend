from __future__ import annotations

import argparse
import hashlib
import os
import re
import secrets
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import urlsplit


POSTGIS_IMAGE = "postgis/postgis:16-3.4"
MARKER_TABLE = "nestify_test_run_identity"
PROTECTED_DATABASE_NAMES = {"nestify", "nestify_pytest"}
RUN_OPT_IN = "NESTIFY_ISOLATED_TEST_RUN"
DATABASE_URL_VARIABLE = "NESTIFY_ISOLATED_DATABASE_URL"
DATABASE_NAME_VARIABLE = "NESTIFY_ISOLATED_DATABASE_NAME"
HOST_VARIABLE = "NESTIFY_ISOLATED_DATABASE_HOST"
PORT_VARIABLE = "NESTIFY_ISOLATED_DATABASE_PORT"
RUN_ID_VARIABLE = "NESTIFY_ISOLATED_RUN_ID"
MARKER_VARIABLE = "NESTIFY_ISOLATED_RUN_MARKER"


class SafeRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseIdentity:
    database_name: str
    server_port: int
    run_id: str
    marker_hash: str
    postgis_version: str | None


def verify_database_identity(
    environment: Mapping[str, str],
    identity_reader: Callable[[str], DatabaseIdentity],
) -> None:
    required = (
        RUN_OPT_IN,
        "DATABASE_URL",
        DATABASE_URL_VARIABLE,
        DATABASE_NAME_VARIABLE,
        HOST_VARIABLE,
        PORT_VARIABLE,
        RUN_ID_VARIABLE,
        MARKER_VARIABLE,
    )
    if any(not environment.get(key) for key in required):
        raise SafeRunnerError(
            "Isolated test database configuration is incomplete"
        )

    if environment[RUN_OPT_IN] != "1":
        raise SafeRunnerError("Explicit isolated test-run opt-in is required")

    database_url = environment[DATABASE_URL_VARIABLE]
    if environment["DATABASE_URL"] != database_url:
        raise SafeRunnerError(
            "DATABASE_URL does not match the runner-owned target"
        )

    try:
        parsed_url = urlsplit(database_url)
        url_port = parsed_url.port
    except ValueError:
        raise SafeRunnerError(
            "Isolated test database URL is malformed"
        ) from None

    database_name = parsed_url.path.removeprefix("/")
    if (
        parsed_url.scheme != "postgresql+psycopg"
        or not parsed_url.hostname
        or url_port is None
        or not parsed_url.username
        or not parsed_url.password
        or not database_name
        or "/" in database_name
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise SafeRunnerError("Isolated test database URL is malformed")

    try:
        expected_port = int(environment[PORT_VARIABLE])
    except ValueError:
        raise SafeRunnerError(
            "Isolated test database port is malformed"
        ) from None

    expected_host = environment[HOST_VARIABLE]
    expected_database = environment[DATABASE_NAME_VARIABLE]
    run_id = environment[RUN_ID_VARIABLE]
    marker = environment[MARKER_VARIABLE]

    if expected_database.lower() in PROTECTED_DATABASE_NAMES:
        raise SafeRunnerError(
            "Protected application database name is not allowed"
        )
    if (
        parsed_url.hostname.lower() != expected_host.lower()
        or url_port != expected_port
        or database_name != expected_database
    ):
        raise SafeRunnerError(
            "Database URL does not match the runner-owned endpoint"
        )
    if not run_id or not marker:
        raise SafeRunnerError("Isolated test-run identity is missing")

    try:
        identity = identity_reader(database_url)
    except Exception:
        raise SafeRunnerError(
            "Could not verify the runner-owned database identity"
        ) from None
    if identity.database_name != expected_database:
        raise SafeRunnerError(
            "Connected database identity does not match the runner"
        )
    if identity.server_port != 5432:
        raise SafeRunnerError(
            "Connected PostgreSQL server identity is unexpected"
        )
    if identity.run_id != run_id:
        raise SafeRunnerError(
            "Connected database belongs to another test run"
        )
    if not secrets.compare_digest(
        identity.marker_hash,
        hashlib.sha256(marker.encode("utf-8")).hexdigest(),
    ):
        raise SafeRunnerError("Connected database run marker does not match")
    if not identity.postgis_version:
        raise SafeRunnerError(
            "PostGIS is unavailable in the isolated database"
        )


def _read_database_identity(database_url: str) -> DatabaseIdentity:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT current_database(), "
                    "inet_server_port(), "
                    "run_id, marker_hash, "
                    "postgis_full_version() "
                    f"FROM {MARKER_TABLE} "
                    "WHERE marker_key = 'current'"
                )
            ).one_or_none()
            if row is None:
                raise SafeRunnerError("Isolated database marker is missing")
            return DatabaseIdentity(
                database_name=row[0],
                server_port=row[1],
                run_id=row[2],
                marker_hash=row[3],
                postgis_version=row[4],
            )
    finally:
        engine.dispose()


def _safe_output(output: str, secrets_to_redact: tuple[str, ...]) -> str:
    sanitized = output
    for secret in secrets_to_redact:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return re.sub(
        r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:/@\s]+):[^@\s]+@",
        r"\1:[REDACTED]@",
        sanitized,
    )


def _run_command(
    command: list[str],
    environment: dict[str, str],
    secrets_to_redact: tuple[str, ...],
) -> int:
    result = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        print(_safe_output(result.stdout, secrets_to_redact), end="")
    if result.stderr:
        print(_safe_output(result.stderr, secrets_to_redact), end="", file=sys.stderr)
    return result.returncode


def run_isolated_tests(pytest_arguments: list[str]) -> int:
    try:
        from testcontainers.postgres import PostgresContainer
        from sqlalchemy import URL, create_engine, text
    except ImportError as exc:
        raise SafeRunnerError(
            "The isolated test runner requires the existing SQLAlchemy and "
            "Testcontainers dependencies"
        ) from exc

    run_id = str(uuid.uuid4())
    marker = secrets.token_urlsafe(32)
    database_name = f"nestify_test_{uuid.uuid4().hex}"
    username = "nestify_test"
    password = secrets.token_urlsafe(32)

    with PostgresContainer(
        image=POSTGIS_IMAGE,
        username=username,
        password=password,
        dbname=database_name,
    ) as container:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(5432))
        database_url = URL.create(
            drivername="postgresql+psycopg",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database_name,
        ).render_as_string(hide_password=False)

        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                connection.execute(
                    text(
                        f"CREATE TABLE {MARKER_TABLE} ("
                        "marker_key text PRIMARY KEY, "
                        "run_id text NOT NULL, "
                        "marker_hash text NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        f"INSERT INTO {MARKER_TABLE} "
                        "(marker_key, run_id, marker_hash) "
                        "VALUES ('current', :run_id, :marker_hash)"
                    ),
                    {
                        "run_id": run_id,
                        # Store only a digest; the raw marker is handed to
                        # the child process solely for identity verification.
                        "marker_hash": hashlib.sha256(
                            marker.encode("utf-8")
                        ).hexdigest(),
                    },
                )
        finally:
            engine.dispose()

        environment = os.environ.copy()
        environment.update(
            {
                RUN_OPT_IN: "1",
                "DATABASE_URL": database_url,
                DATABASE_URL_VARIABLE: database_url,
                DATABASE_NAME_VARIABLE: database_name,
                HOST_VARIABLE: host,
                PORT_VARIABLE: str(port),
                RUN_ID_VARIABLE: run_id,
                MARKER_VARIABLE: marker,
            }
        )
        verify_database_identity(environment, _read_database_identity)

        secrets_to_redact = (database_url, password, marker)
        migration_status = _run_command(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            environment,
            secrets_to_redact,
        )
        if migration_status != 0:
            return migration_status

        arguments = pytest_arguments or ["tests/integration"]
        return _run_command(
            [sys.executable, "-m", "pytest", *arguments],
            environment,
            secrets_to_redact,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run tests against a fresh, runner-owned PostgreSQL/PostGIS "
            "Testcontainers database."
        )
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="arguments forwarded to pytest (default: tests/integration)",
    )
    arguments = parser.parse_args(argv)
    pytest_arguments = arguments.pytest_args
    if pytest_arguments and pytest_arguments[0] == "--":
        pytest_arguments = pytest_arguments[1:]
    try:
        return run_isolated_tests(pytest_arguments)
    except SafeRunnerError as exc:
        print(f"Isolated test run failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Container and database exceptions can contain connection details.
        print(
            f"Isolated test run failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
