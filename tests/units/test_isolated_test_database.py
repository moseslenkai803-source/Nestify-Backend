import hashlib
from dataclasses import replace

import pytest

from scripts.run_isolated_tests import (
    DatabaseIdentity,
    DATABASE_NAME_VARIABLE,
    DATABASE_URL_VARIABLE,
    HOST_VARIABLE,
    MARKER_VARIABLE,
    PORT_VARIABLE,
    RUN_ID_VARIABLE,
    RUN_OPT_IN,
    _safe_output,
    verify_database_identity,
)


def _environment() -> dict[str, str]:
    url = "postgresql+psycopg://user:password@127.0.0.1:49152/nestify_test_run"
    return {
        RUN_OPT_IN: "1",
        "DATABASE_URL": url,
        DATABASE_URL_VARIABLE: url,
        DATABASE_NAME_VARIABLE: "nestify_test_run",
        HOST_VARIABLE: "127.0.0.1",
        PORT_VARIABLE: "49152",
        RUN_ID_VARIABLE: "run-id",
        MARKER_VARIABLE: "secret-marker",
    }


def _identity(environment: dict[str, str]) -> DatabaseIdentity:
    return DatabaseIdentity(
        database_name=environment[DATABASE_NAME_VARIABLE],
        server_port=5432,
        run_id=environment[RUN_ID_VARIABLE],
        marker_hash=hashlib.sha256(
            environment[MARKER_VARIABLE].encode()
        ).hexdigest(),
        postgis_version="POSTGIS=3.4.0",
    )


def test_identity_guard_accepts_matching_runner_owned_database():
    environment = _environment()

    verify_database_identity(
        environment,
        lambda database_url: _identity(environment),
    )


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        (RUN_OPT_IN, "", "configuration is incomplete"),
        (RUN_OPT_IN, "0", "opt-in is required"),
        ("DATABASE_URL", "postgresql+psycopg://unrelated", "does not match"),
        (
            DATABASE_URL_VARIABLE,
            "not a URL",
            "URL is malformed",
        ),
        (
            DATABASE_NAME_VARIABLE,
            "nestify",
            "Protected application database",
        ),
        (HOST_VARIABLE, "localhost", "does not match"),
        (PORT_VARIABLE, "49153", "does not match"),
        (PORT_VARIABLE, "invalid", "port is malformed"),
    ],
)
def test_identity_guard_rejects_invalid_runner_configuration(
    key,
    value,
    message,
):
    environment = _environment()
    environment[key] = value
    if key == DATABASE_URL_VARIABLE:
        environment["DATABASE_URL"] = value

    with pytest.raises(RuntimeError, match=message):
        verify_database_identity(environment, lambda _: pytest.fail("connected"))


@pytest.mark.parametrize(
    ("identity_changes", "message"),
    [
        ({"database_name": "nestify"}, "database identity"),
        ({"server_port": 5433}, "server identity"),
        ({"run_id": "another-run"}, "another test run"),
        ({"marker_hash": "wrong-marker"}, "marker does not match"),
        ({"postgis_version": None}, "PostGIS is unavailable"),
    ],
)
def test_identity_guard_rejects_mismatched_connected_identity(
    identity_changes,
    message,
):
    environment = _environment()
    identity = _identity(environment)
    for key, value in identity_changes.items():
        identity = replace(identity, **{key: value})

    with pytest.raises(RuntimeError, match=message):
        verify_database_identity(environment, lambda _: identity)


def test_identity_guard_does_not_connect_when_configuration_is_missing():
    with pytest.raises(RuntimeError, match="configuration is incomplete"):
        verify_database_identity({}, lambda _: pytest.fail("connected"))


def test_runner_output_redacts_connection_credentials_and_marker():
    environment = _environment()
    url = environment[DATABASE_URL_VARIABLE]
    marker = environment[MARKER_VARIABLE]

    output = _safe_output(
        f"failed for {url} marker={marker}",
        (url, "password", marker),
    )

    assert url not in output
    assert "password" not in output
    assert marker not in output


def test_db_session_fixture_verifies_identity_before_session_creation(
    monkeypatch,
):
    conftest = _load_root_conftest()

    calls = []

    class FakeSession:
        def rollback(self):
            pass

        def close(self):
            pass

    session = FakeSession()

    def verify(environment, identity_reader):
        calls.append("verified")

    def create_session():
        calls.append("session_created")
        return session

    monkeypatch.setattr(conftest, "verify_database_identity", verify)
    monkeypatch.setattr(
        "app.db.session.SessionLocal", create_session
    )

    fixture = conftest.db_session.__wrapped__()

    assert next(fixture) is session
    assert calls == ["verified", "session_created"]

    fixture.close()


def test_db_session_fixture_rejects_database_before_session_creation(
    monkeypatch,
):
    conftest = _load_root_conftest()

    def reject_database(environment, identity_reader):
        raise RuntimeError("Unsafe database")

    def create_session():
        pytest.fail("SessionLocal must not be called")

    monkeypatch.setattr(
        conftest, "verify_database_identity", reject_database
    )
    monkeypatch.setattr(
        "app.db.session.SessionLocal", create_session
    )

    fixture = conftest.db_session.__wrapped__()

    with pytest.raises(RuntimeError, match="Unsafe database"):
        next(fixture)


def _load_root_conftest():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "conftest.py"
    spec = importlib.util.spec_from_file_location(
        "nestify_root_conftest", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
