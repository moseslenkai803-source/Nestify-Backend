import uuid

from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.user import User
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)


def create_employee(db_session) -> Employee:
    user = User(
        email=f"employee-{uuid.uuid4().hex}@example.com",
        password_hash="hashed-password",
        role="employee",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    employee = Employee(
        user_id=user.id,
        employee_number=f"EMP-{uuid.uuid4().hex[:8]}",
        department="Operations",
        position="Operations Officer",
    )
    db_session.add(employee)
    db_session.flush()

    return employee


def create_clearance(
    db_session,
    employee: Employee,
    clearance: str = "plate_operations",
    is_active: bool = True,
) -> EmployeeClearance:
    record = EmployeeClearance(
        employee_id=employee.id,
        clearance=clearance,
        is_active=is_active,
    )
    db_session.add(record)
    db_session.flush()
    return record


def test_add_clearance(db_session):
    employee = create_employee(db_session)
    repository = EmployeeClearanceRepository(db_session)

    clearance = EmployeeClearance(
        employee_id=employee.id,
        clearance="plate_operations",
    )

    result = repository.add(clearance)

    assert result.id is not None
    assert result.employee_id == employee.id
    assert result.clearance == "plate_operations"
    assert result.is_active is True


def test_get_by_id_returns_clearance(db_session):
    employee = create_employee(db_session)
    clearance = create_clearance(db_session, employee)

    repository = EmployeeClearanceRepository(db_session)

    result = repository.get_by_id(clearance.id)

    assert result is not None
    assert result.id == clearance.id


def test_get_by_id_returns_none_for_missing_clearance(db_session):
    repository = EmployeeClearanceRepository(db_session)

    result = repository.get_by_id(uuid.uuid4())

    assert result is None


def test_get_by_id_for_update_returns_clearance(db_session):
    employee = create_employee(db_session)
    clearance = create_clearance(db_session, employee)

    repository = EmployeeClearanceRepository(db_session)

    result = repository.get_by_id_for_update(clearance.id)

    assert result is not None
    assert result.id == clearance.id


def test_get_by_employee_id_returns_clearances(db_session):
    employee = create_employee(db_session)

    first = create_clearance(
        db_session,
        employee,
        clearance="plate_operations",
    )
    second = create_clearance(
        db_session,
        employee,
        clearance="contractor_management",
    )

    repository = EmployeeClearanceRepository(db_session)

    result = repository.get_by_employee_id(employee.id)

    result_ids = {record.id for record in result}

    assert first.id in result_ids
    assert second.id in result_ids


def test_get_active_by_employee_id_excludes_inactive_clearances(
    db_session,
):
    employee = create_employee(db_session)

    active = create_clearance(
        db_session,
        employee,
        clearance="plate_operations",
        is_active=True,
    )
    inactive = create_clearance(
        db_session,
        employee,
        clearance="contractor_management",
        is_active=False,
    )

    repository = EmployeeClearanceRepository(db_session)

    result = repository.get_active_by_employee_id(employee.id)

    result_ids = {record.id for record in result}

    assert active.id in result_ids
    assert inactive.id not in result_ids


def test_get_by_employee_and_clearance_returns_record(db_session):
    employee = create_employee(db_session)

    clearance = create_clearance(
        db_session,
        employee,
        clearance="plate_operations",
    )

    repository = EmployeeClearanceRepository(db_session)

    result = repository.get_by_employee_and_clearance(
        employee.id,
        "plate_operations",
    )

    assert result is not None
    assert result.id == clearance.id
