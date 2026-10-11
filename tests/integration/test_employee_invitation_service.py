from threading import Event, Thread
import uuid


from app.db.session import SessionLocal
from app.models.employee import Employee
from app.models.user import User
from app.services.employee_invitation_service import EmployeeInvitationService


def test_concurrent_invitation_creation_rejects_duplicate_email(db_session):
    admin = User(
        id=uuid.uuid4(),
        email=f"invitation-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    email = f"concurrent-invite-{uuid.uuid4()}@example.com"
    first_session = SessionLocal()
    second_started = Event()
    second_finished = Event()
    second_result = {}

    try:
        first_service = EmployeeInvitationService(first_session)
        first_service.create_invitation(
            email=email,
            employee_number=f"INV-{uuid.uuid4().hex[:12]}",
            department="Operations",
            position="Officer",
            clearances=[],
            invited_by_user_id=admin.id,
        )

        def create_from_second_transaction():
            second_session = SessionLocal()
            try:
                second_started.set()
                EmployeeInvitationService(second_session).create_invitation(
                    email=email,
                    employee_number=f"INV-{uuid.uuid4().hex[:12]}",
                    department="Operations",
                    position="Officer",
                    clearances=[],
                    invited_by_user_id=admin.id,
                )
                second_result["unexpected_success"] = True
            except Exception as exc:
                second_result["error"] = exc
            finally:
                second_session.rollback()
                second_session.close()
                second_finished.set()

        thread = Thread(target=create_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.5)

        first_session.commit()

        assert second_finished.wait(timeout=5)
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert isinstance(second_result.get("error"), ValueError)
        assert str(second_result["error"]) == (
            "An active invitation already exists for this email"
        )
    finally:
        first_session.rollback()
        first_session.close()


def test_concurrent_invitation_creation_rejects_duplicate_employee_number(
    db_session,
):
    admin = User(
        id=uuid.uuid4(),
        email=f"invitation-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    employee_number = f"INV-{uuid.uuid4().hex[:12]}"
    first_session = SessionLocal()
    second_started = Event()
    second_finished = Event()
    second_result = {}

    try:
        EmployeeInvitationService(first_session).create_invitation(
            email=f"first-{uuid.uuid4()}@example.com",
            employee_number=employee_number,
            department="Operations",
            position="Officer",
            clearances=[],
            invited_by_user_id=admin.id,
        )

        def create_from_second_transaction():
            second_session = SessionLocal()
            try:
                second_started.set()
                EmployeeInvitationService(second_session).create_invitation(
                    email=f"second-{uuid.uuid4()}@example.com",
                    employee_number=employee_number,
                    department="Operations",
                    position="Officer",
                    clearances=[],
                    invited_by_user_id=admin.id,
                )
                second_result["unexpected_success"] = True
            except Exception as exc:
                second_result["error"] = exc
            finally:
                second_session.rollback()
                second_session.close()
                second_finished.set()

        thread = Thread(target=create_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.5)

        first_session.commit()

        assert second_finished.wait(timeout=5)
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert isinstance(second_result.get("error"), ValueError)
        assert str(second_result["error"]) == (
            "An active invitation already exists for this employee number"
        )
    finally:
        first_session.rollback()
        first_session.close()

def test_concurrent_invitation_redemption_allows_only_one_employee(db_session):
    admin = User(
        id=uuid.uuid4(),
        email=f"redemption-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    creator_session = SessionLocal()
    first_session = SessionLocal()
    second_started = Event()
    second_finished = Event()
    second_result = {}
    email = f"redeem-{uuid.uuid4()}@example.com"
    employee_number = f"INV-{uuid.uuid4().hex[:12]}"

    try:
        invitation, raw_token = EmployeeInvitationService(
            creator_session
        ).create_invitation(
            email=email,
            employee_number=employee_number,
            department="Operations",
            position="Officer",
            clearances=[],
            invited_by_user_id=admin.id,
        )
        invitation_id = invitation.id
        creator_session.commit()

        first_service = EmployeeInvitationService(first_session)
        first_user, first_employee = first_service.accept_invitation(
            token=raw_token,
            password="SecurePass123!",
        )

        def redeem_from_second_transaction():
            second_session = SessionLocal()
            try:
                second_started.set()
                EmployeeInvitationService(second_session).accept_invitation(
                    token=raw_token,
                    password="AnotherSecurePass123!",
                )
                second_result["unexpected_success"] = True
            except Exception as exc:
                second_result["error"] = exc
            finally:
                second_session.rollback()
                second_session.close()
                second_finished.set()

        thread = Thread(target=redeem_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.5)

        first_session.commit()

        assert second_finished.wait(timeout=5)
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert isinstance(second_result.get("error"), ValueError)
        assert str(second_result["error"]) == "Invitation has already been used"

        verification_session = SessionLocal()
        try:
            assert verification_session.query(User).filter_by(
                email=email
            ).count() == 1
            assert verification_session.query(Employee).filter_by(
                employee_number=employee_number
            ).count() == 1
        finally:
            verification_session.close()
    finally:
        creator_session.rollback()
        creator_session.close()
        first_session.rollback()
        first_session.close()
