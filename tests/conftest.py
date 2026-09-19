import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


@pytest.fixture
def db_session() -> Session:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()
