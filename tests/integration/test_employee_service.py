import uuid
from threading import Event, Thread

import pytest

from app.db.session import SessionLocal

from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.user import User
from app.services.employee_service import EmployeeService


def create_employee_user(
    db_session,
    *,
    role="employee",
    is_active=True,
):
    user = User(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4()}@example.com",
        password_hash="hashed-password",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_create_employee(db_session):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number=" EMP-001 ",
        department=" Operations ",
        position=" Field Officer ",
    )

    assert employee.id is not None
    assert employee.user_id == user.id
    assert employee.employee_number == "EMP-001"
    assert employee.department == "Operations"
    assert employee.position == "Field Officer"
    assert employee.joined_at is not None
    assert employee.ended_at is None


def test_create_employee_normalizes_initial_clearances(db_session):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-002",
        department="Operations",
        position="Officer",
        clearances=[
            " plate_operations ",
            "plate_operations",
            " property_verification ",
        ],
    )

    clearances = service.list_clearances(employee.id)

    assert [item.clearance for item in clearances] == [
        "plate_operations",
        "property_verification",
    ]


def test_create_employee_rejects_missing_user(db_session):
    service = EmployeeService(db_session)

    with pytest.raises(ValueError, match="User not found"):
        service.create_employee(
            user_id=uuid.uuid4(),
            employee_number="EMP-003",
            department="Operations",
            position="Officer",
        )


def test_create_employee_rejects_inactive_user(db_session):
    user = create_employee_user(
        db_session,
        is_active=False,
    )

    service = EmployeeService(db_session)

    with pytest.raises(ValueError, match="User is inactive"):
        service.create_employee(
            user_id=user.id,
            employee_number="EMP-004",
            department="Operations",
            position="Officer",
        )


def test_create_employee_rejects_non_employee_user(db_session):
    user = create_employee_user(
        db_session,
        role="landlord",
    )

    service = EmployeeService(db_session)

    with pytest.raises(
        ValueError,
        match="Only employee users can have employee records",
    ):
        service.create_employee(
            user_id=user.id,
            employee_number="EMP-005",
            department="Operations",
            position="Officer",
        )


def test_create_employee_rejects_duplicate_employee_for_user(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    service.create_employee(
        user_id=user.id,
        employee_number="EMP-006",
        department="Operations",
        position="Officer",
    )

    with pytest.raises(
        ValueError,
        match="User is already an employee",
    ):
        service.create_employee(
            user_id=user.id,
            employee_number="EMP-007",
            department="Operations",
            position="Officer",
        )


def test_create_employee_rejects_duplicate_employee_number(
    db_session,
):
    first_user = create_employee_user(db_session)
    second_user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    service.create_employee(
        user_id=first_user.id,
        employee_number="EMP-008",
        department="Operations",
        position="Officer",
    )

    with pytest.raises(
        ValueError,
        match="Employee number already exists",
    ):
        service.create_employee(
            user_id=second_user.id,
            employee_number="EMP-008",
            department="Operations",
            position="Officer",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("employee_number", "   ", "Employee number is required"),
        ("department", "   ", "Department is required"),
        ("position", "   ", "Position is required"),
    ],
)
def test_create_employee_rejects_blank_required_fields(
    db_session,
    field,
    value,
    message,
):
    user = create_employee_user(db_session)

    values = {
        "employee_number": "EMP-009",
        "department": "Operations",
        "position": "Officer",
    }
    values[field] = value

    service = EmployeeService(db_session)

    with pytest.raises(ValueError, match=message):
        service.create_employee(
            user_id=user.id,
            **values,
        )


def test_get_employee(db_session):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-010",
        department="Operations",
        position="Officer",
    )

    result = service.get_employee(employee.id)

    assert result.id == employee.id


def test_get_employee_rejects_missing_employee(db_session):
    service = EmployeeService(db_session)

    with pytest.raises(ValueError, match="Employee not found"):
        service.get_employee(uuid.uuid4())


def test_list_employees(db_session):
    first_user = create_employee_user(db_session)
    second_user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    first = service.create_employee(
        user_id=first_user.id,
        employee_number="EMP-011",
        department="Operations",
        position="Officer",
    )

    second = service.create_employee(
        user_id=second_user.id,
        employee_number="EMP-012",
        department="Verification",
        position="Verifier",
    )

    employees = service.list_employees()

    assert {employee.id for employee in employees} >= {
        first.id,
        second.id,
    }


def test_list_active_employees_excludes_terminated_employee(
    db_session,
):
    first_user = create_employee_user(db_session)
    second_user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    first = service.create_employee(
        user_id=first_user.id,
        employee_number="EMP-013",
        department="Operations",
        position="Officer",
    )

    second = service.create_employee(
        user_id=second_user.id,
        employee_number="EMP-014",
        department="Verification",
        position="Verifier",
    )

    service.terminate_employee(first.id)

    active = service.list_employees(active_only=True)

    assert first.id not in {employee.id for employee in active}
    assert second.id in {employee.id for employee in active}


def test_add_clearance(db_session):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-015",
        department="Operations",
        position="Officer",
    )

    clearance = service.add_clearance(
        employee_id=employee.id,
        clearance=" plate_operations ",
    )

    assert clearance.clearance == "plate_operations"
    assert clearance.is_active is True


def test_add_clearance_rejects_duplicate_active_clearance(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-016",
        department="Operations",
        position="Officer",
        clearances=["plate_operations"],
    )

    with pytest.raises(
        ValueError,
        match="Employee already has this active clearance",
    ):
        service.add_clearance(
            employee_id=employee.id,
            clearance="plate_operations",
        )


def test_add_clearance_reactivates_removed_clearance(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-017",
        department="Operations",
        position="Officer",
        clearances=["plate_operations"],
    )

    removed = service.remove_clearance(
        employee_id=employee.id,
        clearance="plate_operations",
    )

    assert removed.is_active is False

    reactivated = service.add_clearance(
        employee_id=employee.id,
        clearance="plate_operations",
    )

    assert reactivated.id == removed.id
    assert reactivated.is_active is True


def test_remove_clearance_preserves_record(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-018",
        department="Operations",
        position="Officer",
        clearances=["plate_operations"],
    )

    removed = service.remove_clearance(
        employee_id=employee.id,
        clearance="plate_operations",
    )

    assert removed.is_active is False

    all_clearances = service.list_clearances(employee.id)
    active_clearances = service.list_clearances(
        employee.id,
        active_only=True,
    )

    assert len(all_clearances) == 1
    assert all_clearances[0].id == removed.id
    assert active_clearances == []


def test_remove_clearance_rejects_missing_active_clearance(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-019",
        department="Operations",
        position="Officer",
    )

    with pytest.raises(
        ValueError,
        match="Active employee clearance not found",
    ):
        service.remove_clearance(
            employee_id=employee.id,
            clearance="plate_operations",
        )


def test_terminate_employee_deactivates_user_and_clearances(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-020",
        department="Operations",
        position="Officer",
        clearances=[
            "plate_operations",
            "property_verification",
        ],
    )

    terminated = service.terminate_employee(employee.id)

    assert terminated.id == employee.id
    assert terminated.ended_at is not None
    assert user.is_active is False

    clearances = service.list_clearances(employee.id)

    assert len(clearances) == 2
    assert all(clearance.is_active is False for clearance in clearances)


def test_terminate_employee_preserves_employee_record(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-021",
        department="Operations",
        position="Officer",
    )

    service.terminate_employee(employee.id)

    persisted_employee = (
        db_session.query(Employee)
        .filter(Employee.id == employee.id)
        .one()
    )

    persisted_user = (
        db_session.query(User)
        .filter(User.id == user.id)
        .one()
    )

    assert persisted_employee.ended_at is not None
    assert persisted_user.is_active is False


def test_terminate_employee_rejects_repeated_termination(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-022",
        department="Operations",
        position="Officer",
    )

    service.terminate_employee(employee.id)

    with pytest.raises(
        ValueError,
        match="Employee is already terminated",
    ):
        service.terminate_employee(employee.id)


def test_clearance_operations_reject_terminated_employee(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee = service.create_employee(
        user_id=user.id,
        employee_number="EMP-023",
        department="Operations",
        position="Officer",
    )

    service.terminate_employee(employee.id)

    with pytest.raises(
        ValueError,
        match="Employee is terminated",
    ):
        service.add_clearance(
            employee_id=employee.id,
            clearance="plate_operations",
        )

    with pytest.raises(
        ValueError,
        match="Employee is terminated",
    ):
        service.remove_clearance(
            employee_id=employee.id,
            clearance="plate_operations",
        )


def test_create_employee_serializes_concurrent_creation_for_same_user(
    db_session,
):
    user = create_employee_user(db_session)

    db_session.commit()

    first_session = SessionLocal()

    employee_number_a = (
        f"EMP-CONCURRENT-A-{uuid.uuid4().hex[:12].upper()}"
    )
    employee_number_b = (
        f"EMP-CONCURRENT-B-{uuid.uuid4().hex[:12].upper()}"
    )

    second_started = Event()
    second_finished = Event()
    second_error = {}

    try:
        first_service = EmployeeService(first_session)

        locked_user = (
            first_service.user_repository.get_by_id_for_update(
                user.id
            )
        )

        assert locked_user is not None

        def create_from_second_transaction():
            second_session = SessionLocal()

            try:
                second_service = EmployeeService(second_session)

                second_started.set()

                second_service.create_employee(
                    user_id=user.id,
                    employee_number=employee_number_b,
                    department="Operations",
                    position="Officer",
                )
            except Exception as exc:
                second_error["error"] = exc
                second_session.rollback()
            finally:
                second_session.close()
                second_finished.set()

        thread = Thread(target=create_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.5)

        first_employee = first_service.create_employee(
            user_id=user.id,
            employee_number=employee_number_a,
            department="Operations",
            position="Officer",
        )

        first_session.commit()

        assert first_employee.user_id == user.id

        assert second_finished.wait(timeout=5)
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert len(second_error) == 1
        assert isinstance(second_error["error"], ValueError)
        assert str(second_error["error"]) == (
            "User is already an employee"
        )

        verification_session = SessionLocal()

        try:
            employees = (
                verification_session.query(Employee)
                .filter(Employee.user_id == user.id)
                .all()
            )

            assert len(employees) == 1
            assert employees[0].id == first_employee.id
            assert employees[0].employee_number == employee_number_a
        finally:
            verification_session.rollback()
            verification_session.close()

    finally:
        first_session.close()


def test_terminate_employee_serializes_concurrent_termination(
    db_session,
):
    user = create_employee_user(db_session)

    service = EmployeeService(db_session)

    employee_number = (
        f"EMP-CONCURRENT-{uuid.uuid4().hex[:12].upper()}"
    )

    employee = service.create_employee(
        user_id=user.id,
        employee_number=employee_number,
        department="Operations",
        position="Officer",
        clearances=[
            "plate_operations",
            "property_verification",
        ],
    )

    db_session.commit()

    first_session = SessionLocal()

    second_started = Event()
    second_finished = Event()
    second_error = {}

    try:
        first_service = EmployeeService(first_session)

        locked_employee = (
            first_service.employee_repository.get_by_id_for_update(
                employee.id
            )
        )

        assert locked_employee is not None

        def terminate_from_second_transaction():
            second_session = SessionLocal()

            try:
                second_service = EmployeeService(second_session)

                second_started.set()

                second_service.terminate_employee(employee.id)
            except Exception as exc:
                second_error["error"] = exc
                second_session.rollback()
            finally:
                second_session.close()
                second_finished.set()

        thread = Thread(target=terminate_from_second_transaction)
        thread.start()

        assert second_started.wait(timeout=2)
        assert not second_finished.wait(timeout=0.5)

        first_terminated = first_service.terminate_employee(
            employee.id
        )

        assert first_terminated.ended_at is not None

        first_session.commit()

        assert second_finished.wait(timeout=5)
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert len(second_error) == 1
        assert isinstance(second_error["error"], ValueError)
        assert str(second_error["error"]) == (
            "Employee is already terminated"
        )

        verification_session = SessionLocal()

        try:
            persisted_employee = (
                verification_session.query(Employee)
                .filter(Employee.id == employee.id)
                .one()
            )

            persisted_user = (
                verification_session.query(User)
                .filter(User.id == user.id)
                .one()
            )

            persisted_clearances = (
                verification_session.query(EmployeeClearance)
                .filter(
                    EmployeeClearance.employee_id == employee.id
                )
                .all()
            )

            assert persisted_employee.ended_at is not None
            assert persisted_user.is_active is False
            assert len(persisted_clearances) == 2
            assert all(
                clearance.is_active is False
                for clearance in persisted_clearances
            )

        finally:
            verification_session.rollback()
            verification_session.close()

    finally:
        first_session.close()
