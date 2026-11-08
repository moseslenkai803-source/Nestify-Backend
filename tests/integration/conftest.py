import os
from collections.abc import Generator
from dataclasses import dataclass
from functools import wraps
from threading import Condition

import pytest
from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from scripts.run_isolated_tests import (
    _read_database_identity,
    verify_database_identity,
)


verify_database_identity(
    os.environ,
    _read_database_identity,
)

# Import application modules only after verifying the runner-owned target.
from app.api.rate_limit import get_rate_limit_service  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import SessionLocal, engine, get_db  # noqa: E402
from app.services.rate_limit_service import RateLimitDecision  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "independent_db_transactions: test requires independent committed connections",
    )


class IntegrationRateLimitService:
    """Deterministic limiter for ordinary integration tests."""

    def check(self, **kwargs):
        return RateLimitDecision.ALLOWED


@pytest.fixture(autouse=True)
def override_rate_limit_service():
    """Keep integration tests independent of a live Redis instance."""
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_rate_limit_service] = (
        lambda: IntegrationRateLimitService()
    )
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def _serialize_session_method(method):
    @wraps(method)
    def serialized(self, *args, **kwargs):
        gate = self._connection_gate
        with gate.condition:
            while gate.request_active and not self._is_request_session:
                gate.condition.wait()
            return method(self, *args, **kwargs)

    return serialized


class _ConnectionGate:
    def __init__(self):
        self.condition = Condition()
        self.request_active = False


class _SerializedSession(Session):
    def __init__(
        self,
        *args,
        connection_gate,
        is_request_session,
        **kwargs,
    ):
        self._connection_gate = connection_gate
        self._is_request_session = is_request_session
        super().__init__(*args, **kwargs)

    add = _serialize_session_method(Session.add)
    add_all = _serialize_session_method(Session.add_all)
    begin = _serialize_session_method(Session.begin)
    begin_nested = _serialize_session_method(Session.begin_nested)
    close = _serialize_session_method(Session.close)
    commit = _serialize_session_method(Session.commit)
    connection = _serialize_session_method(Session.connection)
    delete = _serialize_session_method(Session.delete)
    execute = _serialize_session_method(Session.execute)
    expunge = _serialize_session_method(Session.expunge)
    expire = _serialize_session_method(Session.expire)
    flush = _serialize_session_method(Session.flush)
    get = _serialize_session_method(Session.get)
    merge = _serialize_session_method(Session.merge)
    query = _serialize_session_method(Session.query)
    refresh = _serialize_session_method(Session.refresh)
    rollback = _serialize_session_method(Session.rollback)
    scalar = _serialize_session_method(Session.scalar)
    scalars = _serialize_session_method(Session.scalars)


@dataclass
class _RequestDatabaseState:
    session: _SerializedSession
    active_dependencies: int = 0
    failed: bool = False


@pytest.fixture
def api_request_sessions():
    return []


@pytest.fixture
def db_session(request, api_request_sessions) -> Generator[Session, None, None]:
    if request.node.get_closest_marker("independent_db_transactions"):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.rollback()
            db.close()
        return

    connection = engine.connect()
    outer_transaction = connection.begin()
    connection_gate = _ConnectionGate()
    sessions = sessionmaker(
        bind=connection,
        class_=_SerializedSession,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
        connection_gate=connection_gate,
        is_request_session=False,
    )
    db = sessions()
    previous_override = app.dependency_overrides.get(get_db)
    had_previous_override = get_db in app.dependency_overrides
    request_state_key = "_nestify_integration_db_session"

    def request_db(request: Request):
        state = request.scope.setdefault("state", {})
        with connection_gate.condition:
            request_database = state.get(request_state_key)
            if request_database is None:
                while connection_gate.request_active:
                    connection_gate.condition.wait()
                request_database = state.get(request_state_key)
                if request_database is None:
                    request_session = sessions(is_request_session=True)
                    request_database = _RequestDatabaseState(request_session)
                    connection_gate.request_active = True
                    state[request_state_key] = request_database
                    api_request_sessions.append(request_session)
            request_database.active_dependencies += 1

        try:
            yield request_database.session
        except BaseException:
            with connection_gate.condition:
                request_database.failed = True
            raise
        finally:
            with connection_gate.condition:
                request_database.active_dependencies -= 1
                if request_database.active_dependencies == 0:
                    try:
                        if request_database.failed:
                            request_database.session.rollback()
                        else:
                            try:
                                request_database.session.commit()
                            except Exception:
                                request_database.session.rollback()
                                raise
                    finally:
                        try:
                            request_database.session.close()
                        finally:
                            state.pop(request_state_key, None)
                            connection_gate.request_active = False
                            connection_gate.condition.notify_all()

    app.dependency_overrides[get_db] = request_db

    try:
        yield db
    finally:
        try:
            db.close()
        finally:
            try:
                if outer_transaction.is_active:
                    outer_transaction.rollback()
            finally:
                try:
                    connection.close()
                finally:
                    if had_previous_override:
                        app.dependency_overrides[get_db] = previous_override
                    else:
                        app.dependency_overrides.pop(get_db, None)
