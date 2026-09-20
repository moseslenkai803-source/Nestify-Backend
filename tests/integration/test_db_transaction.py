import uuid

from app.db.session import SessionLocal, get_db
from app.models.user import User


def test_get_db_commits_successful_transaction():
    email = f"transaction-{uuid.uuid4()}@example.com"

    db_generator = get_db()
    db = next(db_generator)

    try:
        user = User(
            email=email,
            password_hash="test-hash",
            role="landlord",
        )

        db.add(user)
        db.flush()

    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass

    verification_db = SessionLocal()

    try:
        user = (
            verification_db.query(User)
            .filter(User.email == email)
            .first()
        )

        assert user is not None
        assert user.email == email

    finally:
        verification_db.rollback()
        verification_db.close()


def test_get_db_rolls_back_failed_transaction():
    email = f"rollback-{uuid.uuid4()}@example.com"

    db_generator = get_db()
    db = next(db_generator)

    user = User(
        email=email,
        password_hash="test-hash",
        role="landlord",
    )

    db.add(user)
    db.flush()

    try:
        db_generator.throw(RuntimeError("simulated request failure"))
    except RuntimeError:
        pass

    verification_db = SessionLocal()

    try:
        user = (
            verification_db.query(User)
            .filter(User.email == email)
            .first()
        )

        assert user is None

    finally:
        verification_db.rollback()
        verification_db.close()
