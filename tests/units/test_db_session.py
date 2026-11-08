from unittest.mock import Mock, patch

import pytest

from app.db.session import get_db


def test_get_db_commits_and_closes_on_success():
    db = Mock()

    with patch("app.db.session.SessionLocal", return_value=db):
        dependency = get_db()
        session = next(dependency)

        assert session is db

        with pytest.raises(StopIteration):
            next(dependency)

    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_get_db_rolls_back_and_closes_on_exception():
    db = Mock()
    error = RuntimeError("request failed")

    with patch("app.db.session.SessionLocal", return_value=db):
        dependency = get_db()
        next(dependency)

        with pytest.raises(RuntimeError, match="request failed"):
            dependency.throw(error)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_get_db_rolls_back_and_closes_on_commit_failure():
    db = Mock()
    db.commit.side_effect = RuntimeError("commit failed")

    with patch("app.db.session.SessionLocal", return_value=db):
        dependency = get_db()
        next(dependency)

        with pytest.raises(RuntimeError, match="commit failed"):
            next(dependency)

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.close.assert_called_once()


def test_get_db_commit_failure_prevents_success_response():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    db = Mock()
    db.commit.side_effect = RuntimeError("commit failed")

    app = FastAPI()

    @app.get("/transaction")
    def transaction_endpoint(session=Depends(get_db, scope="function")):
        return {"ok": True}

    with patch("app.db.session.SessionLocal", return_value=db):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/transaction")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.close.assert_called_once()
