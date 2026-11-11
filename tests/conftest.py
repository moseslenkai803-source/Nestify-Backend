from collections.abc import Generator
from os import environ

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from scripts.run_isolated_tests import (
    _read_database_identity,
    verify_database_identity,
)


def pytest_ignore_collect(collection_path, config):
    if (
        collection_path.name == "test_property_location_migration_upgrade.py"
        and environ.get("RUN_MIGRATION_TESTS") != "1"
    ):
        return True
    return None


def cleanup_installation_test_context(
    db: Session,
    property_id,
    user_ids,
    manufacturing_order_id=None,
    dispatch_id=None,
    plate_ids=None,
) -> None:
    plate_ids = list(plate_ids or [])
    plate_filter = " OR plate_id = ANY(:plate_ids)" if plate_ids else ""
    plate_record_filter = " OR id = ANY(:plate_ids)" if plate_ids else ""

    cleanup_params = {
        "property_id": property_id,
        "manufacturing_order_id": manufacturing_order_id,
    }
    if plate_ids:
        cleanup_params["plate_ids"] = plate_ids

    db.execute(
        text(
            "DELETE FROM property_installation_verifications "
            "WHERE installation_id IN ("
            "SELECT id FROM property_installations "
            "WHERE property_id = :property_id" + plate_filter + ")"
        ),
        cleanup_params,
    )

    db.execute(
        text(
            "DELETE FROM address_plate_lifecycle_events "
            "WHERE plate_id IN ("
            "SELECT id FROM address_plates "
            "WHERE property_id = :property_id "
            "OR manufacturing_order_id = :manufacturing_order_id"
            + plate_record_filter + ")"
        ),
        cleanup_params,
    )

    db.execute(
        text(
            "DELETE FROM property_installations "
            "WHERE property_id = :property_id" + plate_filter
        ),
        cleanup_params,
    )

    db.execute(
        text(
            "DELETE FROM installation_assignments "
            "WHERE property_id = :property_id" + plate_filter
        ),
        cleanup_params,
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
            "DELETE FROM dispatch_items "
            "WHERE plate_id IN ("
            "SELECT id FROM address_plates "
            "WHERE property_id = :property_id "
            "OR manufacturing_order_id = :manufacturing_order_id)"
            + plate_filter + " OR dispatch_id = :dispatch_id"
        ),
        {
            "property_id": property_id,
            "manufacturing_order_id": manufacturing_order_id,
            "dispatch_id": dispatch_id,
            **({"plate_ids": plate_ids} if plate_ids else {}),
        },
    )

    db.execute(
        text(
            "DELETE FROM dispatches "
            "WHERE id = :dispatch_id"
        ),
        {"dispatch_id": dispatch_id},
    )

    db.execute(
        text(
            "DELETE FROM address_plate_requests "
            "WHERE property_id = :property_id"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM address_plates "
            "WHERE property_id = :property_id "
            "OR manufacturing_order_id = :manufacturing_order_id"
            + plate_record_filter
        ),
        cleanup_params,
    )

    db.execute(
        text(
            "DELETE FROM manufacturing_orders "
            "WHERE id = :manufacturing_order_id"
        ),
        {"manufacturing_order_id": manufacturing_order_id},
    )

    db.execute(
        text(
            "DELETE FROM property_access "
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
        text(
            "DELETE FROM property_location_verifications "
            "WHERE location_id IN ("
            "SELECT id FROM property_locations "
            "WHERE property_id = :property_id)"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text(
            "DELETE FROM property_locations "
            "WHERE property_id = :property_id"
        ),
        {"property_id": property_id},
    )

    db.execute(
        text("DELETE FROM properties WHERE id = :property_id"),
        {"property_id": property_id},
    )

    for landlord_id in landlord_ids:
        db.execute(
            text("DELETE FROM landlords WHERE id = :landlord_id"),
            {"landlord_id": landlord_id},
        )

    db.execute(
        text(
            "DELETE FROM employee_clearances "
            "WHERE employee_id IN ("
            "SELECT id FROM employees "
            "WHERE user_id = ANY(:user_ids))"
        ),
        {"user_ids": user_ids},
    )

    db.execute(
        text(
            "DELETE FROM employees "
            "WHERE user_id = ANY(:user_ids)"
        ),
        {"user_ids": user_ids},
    )

    for user_id in user_ids:
        db.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )

    db.commit()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    verify_database_identity(environ, _read_database_identity)

    from app.db.session import SessionLocal

    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()
