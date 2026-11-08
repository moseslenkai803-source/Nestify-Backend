import importlib.util
from pathlib import Path

import pytest


_MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "a94c2e7d61f0_version_property_locations.py"
)
_LOCK_SQL = (
    "LOCK TABLE property_locations, property_location_verifications "
    "IN SHARE ROW EXCLUSIVE MODE"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "versioned_property_locations_migration",
        _MIGRATION_PATH,
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


class _Connection:
    def __init__(self, has_location_history, expected_predicates=()):
        self.has_location_history = has_location_history
        self.expected_predicates = expected_predicates
        self.events = []

    def execute(self, statement):
        sql = str(statement)
        self.events.append(("execute", sql))

    def scalar(self, statement):
        assert self.events == [("execute", _LOCK_SQL)]
        sql = str(statement)
        for expected_predicate in self.expected_predicates:
            assert expected_predicate in sql
        self.events.append(("safety_check", sql))
        return self.has_location_history


def _patch_downgrade(migration, monkeypatch, connection):
    destructive_operations = []
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

    for operation in (
        "drop_index",
        "drop_table",
        "drop_constraint",
        "create_foreign_key",
        "drop_column",
        "create_check_constraint",
        "create_index",
    ):
        monkeypatch.setattr(
            migration.op,
            operation,
            lambda *args, _operation=operation, **kwargs: (
                destructive_operations.append(_operation)
            ),
        )

    return destructive_operations


@pytest.mark.parametrize(
    "history_case, expected_predicates",
    [
        (
            "verification_decision_exists",
            "EXISTS (SELECT 1 FROM property_location_verifications)",
        ),
        (
            "multiple_location_versions_exist",
            "GROUP BY property_id HAVING COUNT(*) > 1",
        ),
        (
            "new_location_status_or_current_state_exists",
            (
                "WHERE status <> 'unverified'",
                "OR version_number <> 1",
                "OR submitted_by_id IS NOT NULL",
                "OR submitted_at IS NOT NULL",
                "OR is_current IS TRUE",
            ),
        ),
    ],
)
def test_downgrade_refuses_location_history_before_destructive_ddl(
    monkeypatch,
    history_case,
    expected_predicates,
):
    assert history_case
    migration = _load_migration()
    connection = _Connection(
        has_location_history=True,
        expected_predicates=expected_predicates,
    )
    destructive_operations = _patch_downgrade(
        migration,
        monkeypatch,
        connection,
    )

    with pytest.raises(RuntimeError, match="would be lost"):
        migration.downgrade()

    assert connection.events[0] == ("execute", _LOCK_SQL)
    assert connection.events[1][0] == "safety_check"
    assert destructive_operations == []


def test_downgrade_allows_legacy_compatible_locations(monkeypatch):
    migration = _load_migration()
    connection = _Connection(has_location_history=False)
    destructive_operations = _patch_downgrade(
        migration,
        monkeypatch,
        connection,
    )

    migration.downgrade()

    assert connection.events[0] == ("execute", _LOCK_SQL)
    assert connection.events[1][0] == "safety_check"
    assert destructive_operations
