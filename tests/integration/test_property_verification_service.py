import uuid
from threading import Event, Thread

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.property_verification import PropertyVerification
from app.models.user import User
from app.repositories.property_verification_repository import PropertyVerificationRepository
 
from app.services.property_verification_service import PropertyVerificationService


def create_verified_property(db_session):
    employee = User(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

    landlord_user = User(
        id=uuid.uuid4(),
        email=f"landlord-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=landlord_user.id,
        display_name="Verification Service Landlord",
        phone="+254700000020",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Verification Service Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(employee)
    db_session.add(landlord_user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    return employee, property_record


def add_property_address(db_session, property_id):
    address = PropertyAddress(
        id=uuid.uuid4(),
        property_id=property_id,
        formatted_address="123 Verification Street, Nairobi, Kenya",
        county="Nairobi",
        sub_county="Westlands",
        locality="Nairobi",
        latitude=-1.286389,
        longitude=36.817223,
    )

    db_session.add(address)
    db_session.flush()
    return address


def test_verify_property_serializes_concurrent_verification_attempts(
    db_session,
):
    employee_one, property_record = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    employee_two = User(
        id=uuid.uuid4(),
        email=f"employee-two-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )
    db_session.add(employee_two)
    db_session.flush()

    property_id = property_record.id
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_locked = Event()
    second_started = Event()
    second_finished = Event()
    second_result = {}
    thread = None

    try:
        first_service = PropertyVerificationService(first_session)

        locked_property = first_service.property_repository.get_by_id_for_update(
            property_id
        )

        assert locked_property is not None
        assert locked_property.status == "draft"

        first_locked.set()

        def verify_from_second_transaction():
            try:
                second_service = PropertyVerificationService(second_session)
                second_started.set()

                second_result["result"] = second_service.verify_property(
                    property_id=property_id,
                    verified_by=employee_two.id,
                    status="verified",
                )
            except Exception as exc:
                second_result["error"] = exc
            finally:
                second_finished.set()

        thread = Thread(target=verify_from_second_transaction)
        thread.start()

        assert first_locked.is_set()
        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.2)

        first_result = first_service.verify_property(
            property_id=property_id,
            verified_by=employee_one.id,
            status="verified",
        )

        assert first_result.status == "verified"
        first_session.commit()

        assert second_finished.wait(timeout=2)
        thread.join(timeout=2)

        assert "error" not in second_result
        assert second_result["result"].status == "verified"

        second_session.commit()

        verifications = PropertyVerificationRepository(
            second_session
        ).get_by_property_id(property_id)
        assert len(verifications) == 2
        assert {verification.verified_by for verification in verifications} == {
            employee_one.id,
            employee_two.id,
        }

    finally:
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()

def test_database_rejects_invalid_property_verification_status(db_session):
    employee, property_record = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    verification = PropertyVerification(
        property_id=property_record.id,
        verified_by=employee.id,
        status="pending",
    )

    db_session.add(verification)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_verify_property_creates_verified_record_and_updates_property(
    db_session,
):
    employee, property_record = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    result = service.verify_property(
        property_id=property_record.id,
        verified_by=employee.id,
        status="verified",
        notes="All required information verified",
    )

    assert result.property_id == property_record.id
    assert result.verified_by == employee.id
    assert result.status == "verified"
    assert result.notes == "All required information verified"
    assert result.verified_at is not None
    assert property_record.status == "verified"


def test_rejected_property_verification_preserves_property_status(
    db_session,
):
    employee, property_record = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    result = service.verify_property(
        property_id=property_record.id,
        verified_by=employee.id,
        status="rejected",
        notes="Additional information required",
    )

    assert result.status == "rejected"
    assert result.notes == "Additional information required"
    assert property_record.status == "draft"


def test_verify_property_requires_existing_property(db_session):
    employee = User(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="employee",
        clearance="property_verification",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    service = PropertyVerificationService(db_session)

    with pytest.raises(ValueError, match="Property not found"):
        service.verify_property(
            property_id=uuid.uuid4(),
            verified_by=employee.id,
            status="verified",
        )


def test_verify_property_requires_address(db_session):
    employee, property_record = create_verified_property(db_session)

    service = PropertyVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Property must have an address before verification",
    ):
        service.verify_property(
            property_id=property_record.id,
            verified_by=employee.id,
            status="verified",
        )


def test_verify_property_does_not_require_active_address_plate(
    db_session,
):
    employee, property_record = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    result = service.verify_property(
        property_id=property_record.id,
        verified_by=employee.id,
        status="verified",
    )

    assert result.property_id == property_record.id
    assert result.status == "verified"
    assert property_record.status == "verified"


def test_verify_property_rejects_invalid_status(db_session):
    employee, property_record = create_verified_property(db_session)
    add_property_address(db_session, property_record.id)

    service = PropertyVerificationService(db_session)

    with pytest.raises(
        ValueError,
        match="Verification status must be 'verified' or 'rejected'",
    ):
        service.verify_property(
            property_id=property_record.id,
            verified_by=employee.id,
            status="pending",
        )
