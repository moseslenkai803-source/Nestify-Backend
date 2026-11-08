import uuid
from threading import Event, Thread

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.main import app
from app.models.user import User


def _register_landlord(email):
    return TestClient(app).post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": "Transaction Test Landlord",
            "phone": "+254700000000",
            "landlord_type": "individual",
        },
    )


def _user_exists(email):
    verification_session = SessionLocal()
    try:
        return (
            verification_session.scalar(
                select(User.id).where(User.email == email)
            )
            is not None
        )
    finally:
        verification_session.close()


def test_ordinary_db_session_write_is_removed_by_outer_rollback(db_session):
    email = f"outer-rollback-{uuid.uuid4()}@example.com"
    db_session.add(
        User(email=email, password_hash="test-hash", role="landlord")
    )
    db_session.commit()

    outer_transaction = db_session.connection().get_transaction()
    assert outer_transaction is not None
    assert outer_transaction.is_active
    assert not _user_exists(email)

    db_session.close()
    outer_transaction.rollback()

    assert not _user_exists(email)


def test_api_commit_stays_inside_outer_transaction(
    db_session,
    api_request_sessions,
):
    email = f"api-commit-{uuid.uuid4()}@example.com"

    response = _register_landlord(email)

    assert response.status_code == 201, response.text
    assert len(api_request_sessions) == 1
    assert api_request_sessions[0] is not db_session
    assert not api_request_sessions[0].in_transaction()

    outer_transaction = db_session.connection().get_transaction()
    assert outer_transaction is not None
    assert outer_transaction.is_active
    assert not _user_exists(email)

    db_session.close()
    outer_transaction.rollback()

    assert not _user_exists(email)


def test_sequential_requests_get_distinct_sessions_without_shared_state(
    db_session,
    api_request_sessions,
):
    first_email = f"api-first-{uuid.uuid4()}@example.com"
    second_email = f"api-second-{uuid.uuid4()}@example.com"

    first_response = _register_landlord(first_email)
    assert first_response.status_code == 201, first_response.text
    first_session = api_request_sessions[-1]
    first_session.info["request_state"] = "first-request"

    second_response = _register_landlord(second_email)
    assert second_response.status_code == 201, second_response.text
    second_session = api_request_sessions[-1]

    assert len(api_request_sessions) == 2
    assert first_session is not second_session
    assert "request_state" not in second_session.info
    assert _user_exists(first_email) is False
    assert _user_exists(second_email) is False


def test_failed_request_rolls_back_and_closes_its_session(
    db_session,
    api_request_sessions,
):
    email = f"api-failure-{uuid.uuid4()}@example.com"

    def fail_after_write(db: Session = Depends(get_db)):
        db.add(User(email=email, password_hash="test-hash", role="landlord"))
        db.flush()
        raise RuntimeError("simulated request failure")

    path = f"/__transaction-isolation/{uuid.uuid4()}"
    app.add_api_route(path, fail_after_write, methods=["POST"])
    test_route = app.router.routes[-1]
    try:
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).post(path)
    finally:
        app.router.routes.remove(test_route)

    assert response.status_code == 500
    assert len(api_request_sessions) == 1
    assert not api_request_sessions[0].in_transaction()
    assert not _user_exists(email)


def test_concurrent_api_requests_use_distinct_serialized_sessions(
    db_session,
    api_request_sessions,
):
    first_request_started = Event()
    second_request_attempting = Event()
    second_request_started = Event()
    allow_first_request_to_finish = Event()
    responses = {}
    errors = []

    def mark_second_request_attempting(request: Request):
        if request.headers["x-test-request"] == "second":
            second_request_attempting.set()

    def coordinate_requests(
        request: Request,
        _=Depends(mark_second_request_attempting),
        db: Session = Depends(get_db),
    ):
        request_id = request.headers["x-test-request"]

        if request_id == "first":
            first_request_started.set()
            if not allow_first_request_to_finish.wait(timeout=5):
                raise TimeoutError("first request was not released")
        else:
            second_request_started.set()

        return {"request_id": request_id}

    path = f"/__transaction-isolation-concurrent/{uuid.uuid4()}"
    app.add_api_route(path, coordinate_requests, methods=["POST"])
    test_route = app.router.routes[-1]

    def send_request(request_id):
        try:
            responses[request_id] = TestClient(app).post(
                path,
                headers={"x-test-request": request_id},
            )
        except Exception as error:
            errors.append(error)

    first_thread = Thread(target=send_request, args=("first",))
    second_thread = Thread(target=send_request, args=("second",))

    first_thread.start()
    try:
        assert first_request_started.wait(timeout=5)

        second_thread.start()
        assert second_request_attempting.wait(timeout=5)

        # The second route must wait while the first request owns the connection.
        assert not second_request_started.wait(timeout=0.1)
    finally:
        allow_first_request_to_finish.set()
        first_thread.join(timeout=5)

        if second_thread.ident is not None:
            second_thread.join(timeout=5)

        app.router.routes.remove(test_route)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert not errors
    assert set(responses) == {"first", "second"}
    assert responses["first"].status_code == 200, responses["first"].text
    assert responses["second"].status_code == 200, responses["second"].text
    assert second_request_started.is_set()

    assert len(api_request_sessions) == 2
    assert api_request_sessions[0] is not api_request_sessions[1]
    assert all(
        not session.in_transaction()
        for session in api_request_sessions
    )


def test_request_and_test_session_access_are_serialized(db_session):
    request_started = Event()
    allow_request_to_finish = Event()
    session_operation_finished = Event()
    responses = []
    errors = []

    def hold_request(db: Session = Depends(get_db)):
        request_started.set()
        if not allow_request_to_finish.wait(timeout=5):
            raise TimeoutError("test request was not released")
        return {"ok": True}

    path = f"/__transaction-isolation-lock/{uuid.uuid4()}"
    app.add_api_route(path, hold_request, methods=["POST"])
    test_route = app.router.routes[-1]

    def send_request():
        try:
            responses.append(TestClient(app).post(path))
        except Exception as error:
            errors.append(error)

    request_thread = Thread(target=send_request)
    session_thread = Thread(
        target=lambda: (
            db_session.scalar(select(1)),
            session_operation_finished.set(),
        )
    )
    request_thread.start()
    try:
        assert request_started.wait(timeout=5)
        session_thread.start()
        assert not session_operation_finished.wait(timeout=0.1)
    finally:
        allow_request_to_finish.set()
        request_thread.join(timeout=5)
        if session_thread.ident is not None:
            session_thread.join(timeout=5)
        app.router.routes.remove(test_route)

    assert not request_thread.is_alive()
    assert not session_thread.is_alive()
    assert not errors
    assert len(responses) == 1
    assert responses[0].status_code == 200
    assert session_operation_finished.is_set()


@pytest.mark.independent_db_transactions
def test_independent_transaction_tests_keep_committed_visibility(db_session):
    email = f"independent-transaction-{uuid.uuid4()}@example.com"
    db_session.add(
        User(email=email, password_hash="test-hash", role="landlord")
    )
    db_session.commit()

    assert _user_exists(email)
