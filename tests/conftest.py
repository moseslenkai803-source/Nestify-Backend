import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


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
def db_session() -> Session:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()
