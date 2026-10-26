from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine


# Tests must use their isolated database, never development or shared test data.
_EXPECTED_TEST_DATABASE = "nestify_pytest"
_CONFIGURED_DATABASE = engine.url.database

if _CONFIGURED_DATABASE != _EXPECTED_TEST_DATABASE:
    raise RuntimeError(
        "Refusing to run tests against database "
        f"{_CONFIGURED_DATABASE!r}. "
        "Set DATABASE_URL to the dedicated 'nestify_pytest' database."
    )


def cleanup_installation_test_context(
    db: Session,
    property_id,
    user_ids,
) -> None:
    db.execute(
        text(
            "DELETE FROM property_installation_verifications "
            "WHERE installation_id IN ("
            "SELECT id FROM property_installations "
            "WHERE property_id = :property_id)"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM address_plate_lifecycle_events "
            "WHERE plate_id IN ("
            "SELECT id FROM address_plates "
            "WHERE property_id = :property_id)"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM property_installations "
            "WHERE property_id = :property_id"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM property_verifications "
            "WHERE property_id = :property_id"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM property_addresses "
            "WHERE property_id = :property_id"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM address_plates "
            "WHERE property_id = :property_id"
        ),
        {"property_id": property_id},
    )

    landlord_ids = [
        row[0]
        for row in db.execute(
            text(
                "SELECT landlord_id FROM properties "
                "WHERE id = :property_id"
            ),
            {"property_id": property_id},
        ).all()
    ]

    db.execute(
        text("DELETE FROM properties WHERE id = :property_id"),
        {"property_id": property_id},
    )

    for landlord_id in landlord_ids:
        db.execute(
            text("DELETE FROM landlords WHERE id = :landlord_id"),
            {"landlord_id": landlord_id},
        )

    for user_id in user_ids:
        db.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )

    db.commit()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()
