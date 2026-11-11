from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    # The request dependency owns this transaction: successful requests commit,
    # while exceptions and commit failures roll it back.
    db = SessionLocal()

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    else:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    finally:
        db.close()
