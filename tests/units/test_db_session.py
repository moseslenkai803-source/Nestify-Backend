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
