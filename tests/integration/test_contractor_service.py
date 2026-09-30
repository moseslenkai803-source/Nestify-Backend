import uuid
from threading import Event, Thread

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.user import User
from app.services.contractor_service import ContractorService


def create_contractor_context(db_session):
    contractor = Contractor(
        id=uuid.uuid4(),
        name="Concurrent Contractor",
        contractor_type="company",
        status="active",
    )

    contractor_user = User(
        id=uuid.uuid4(),
        email=f"contractor-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role="contractor",
        is_active=True,
    )

    db_session.add(contractor)
    db_session.add(contractor_user)
    db_session.flush()

    return {
        "contractor": contractor,
        "contractor_user": contractor_user,
    }


def test_add_member_serializes_concurrent_membership_creation(
    db_session,
):
    context = create_contractor_context(db_session)

    contractor_id = context["contractor"].id
    user_id = context["contractor_user"].id

    # Make the records visible to independent transactions.
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()

    first_service = ContractorService(first_session)
    second_service = ContractorService(second_session)

    started = Event()
    finished = Event()
    errors = []

    try:
        # Transaction A acquires the contractor serialization lock.
        first_service.contractor_repository.get_by_id_for_update(
            contractor_id
        )
        first_session.flush()

        def concurrent_add_member():
            started.set()

            try:
                second_service.add_member(
                    contractor_id=contractor_id,
                    user_id=user_id,
                )
                second_session.commit()
            except Exception as exc:
                second_session.rollback()
                errors.append(exc)
            finally:
                finished.set()

        thread = Thread(target=concurrent_add_member)
        thread.start()

        # Transaction B should reach the contractor lock and wait.
        assert started.wait(timeout=2)
        assert not finished.wait(timeout=0.5)

        # Transaction A wins the race and creates the membership.
        first_service.add_member(
            contractor_id=contractor_id,
            user_id=user_id,
        )
        first_session.commit()

        thread.join(timeout=2)

        assert finished.is_set()
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
        assert str(errors[0]) == (
            "User is already an active member of this contractor"
        )

        verification_session = SessionLocal()

        try:
            memberships = (
                verification_session.query(ContractorMember)
                .filter(
                    ContractorMember.contractor_id == contractor_id,
                    ContractorMember.user_id == user_id,
                )
                .all()
            )

            assert len(memberships) == 1
            assert memberships[0].is_active is True
        finally:
            verification_session.close()

    finally:
        if not finished.is_set():
            second_session.rollback()

        first_session.close()
        second_session.close()

def test_database_rejects_invalid_contractor_status(db_session):
    contractor = Contractor(
        name="Invalid Status Contractor",
        contractor_type="company",
        status="invalid_status",
    )
    db_session.add(contractor)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
