import uuid
from datetime import UTC, datetime

from app.models.employee import Employee
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository


def create_user(
    db_session,
    *,
    email: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex}@example.com",
        password_hash="hashed-password",
        role="employee",
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_employee(
    db_session,
    *,
    user: User | None = None,
    employee_number: str | None = None,
    ended_at=None,
) -> Employee:
    user = user or create_user(db_session)

    employee = Employee(
        user_id=user.id,
        employee_number=employee_number
        or f"EMP-{uuid.uuid4().hex[:8]}",
        department="Operations",
        position="Operations Officer",
        ended_at=ended_at,
    )
    db_session.add(employee)
    db_session.flush()
    return employee


def test_add_employee(db_session):
    user = create_user(db_session)
    repository = EmployeeRepository(db_session)

    employee = Employee(
        user_id=user.id,
        employee_number="EMP-0001",
        department="Operations",
        position="Operations Officer",
    )

    result = repository.add(employee)

    assert result.id is not None
    assert result.user_id == user.id
    assert result.employee_number == "EMP-0001"


def test_get_by_id_returns_employee(db_session):
    employee = create_employee(db_session)
    repository = EmployeeRepository(db_session)

    result = repository.get_by_id(employee.id)

    assert result is not None
    assert result.id == employee.id


def test_get_by_id_returns_none_for_missing_employee(db_session):
    repository = EmployeeRepository(db_session)

    result = repository.get_by_id(uuid.uuid4())

    assert result is None


def test_get_by_id_for_update_returns_employee(db_session):
    employee = create_employee(db_session)
    repository = EmployeeRepository(db_session)

    result = repository.get_by_id_for_update(employee.id)

    assert result is not None
    assert result.id == employee.id


def test_get_by_id_for_update_returns_none_for_missing_employee(
    db_session,
):
    repository = EmployeeRepository(db_session)

    result = repository.get_by_id_for_update(uuid.uuid4())

    assert result is None


def test_get_by_user_id_returns_employee(db_session):
    user = create_user(db_session)
    employee = create_employee(db_session, user=user)

    repository = EmployeeRepository(db_session)

    result = repository.get_by_user_id(user.id)

    assert result is not None
    assert result.id == employee.id


def test_get_by_employee_number_returns_employee(db_session):
    employee = create_employee(
        db_session,
        employee_number="EMP-LOOKUP",
    )

    repository = EmployeeRepository(db_session)

    result = repository.get_by_employee_number("EMP-LOOKUP")

    assert result is not None
    assert result.id == employee.id


def test_get_all_returns_employees(db_session):
    first = create_employee(db_session)
    second = create_employee(db_session)

    repository = EmployeeRepository(db_session)

    result = repository.get_all()

    result_ids = {employee.id for employee in result}

    assert first.id in result_ids
    assert second.id in result_ids


def test_get_active_returns_active_employees_only(db_session):
    active_user = create_user(
        db_session,
        email="active@example.com",
        is_active=True,
    )
    inactive_user = create_user(
        db_session,
        email="inactive@example.com",
        is_active=False,
    )
    ended_user = create_user(
        db_session,
        email="ended@example.com",
        is_active=True,
    )

    active_employee = create_employee(
        db_session,
        user=active_user,
        employee_number="EMP-ACTIVE",
    )
    inactive_employee = create_employee(
        db_session,
        user=inactive_user,
        employee_number="EMP-INACTIVE",
    )
    ended_employee = create_employee(
        db_session,
        user=ended_user,
        employee_number="EMP-ENDED",
        ended_at=datetime.now(UTC),
    )

    repository = EmployeeRepository(db_session)

    result = repository.get_active()

    result_ids = {employee.id for employee in result}

    assert active_employee.id in result_ids
    assert inactive_employee.id not in result_ids
    assert ended_employee.id not in result_ids
