from datetime import date

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Department, Employee, User, UserRole


def test_initial_migration_creates_expected_tables(
    postgres_engine: Engine,
) -> None:
    inspector = inspect(postgres_engine)

    assert {"departments", "employees", "users", "alembic_version"} <= set(
        inspector.get_table_names()
    )

    with postgres_engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    expected_revision = ScriptDirectory.from_config(
        Config("alembic.ini")
    ).get_current_head()
    assert revision == expected_revision


def test_models_create_and_relationships_work(db_session: Session) -> None:
    department = Department(name="Engineering", description="Platform team")
    employee = Employee(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        hire_date=date(2024, 1, 15),
        department=department,
    )
    user = User(
        email="ada.user@example.com",
        hashed_password="hashed-value",
        role=UserRole.EMPLOYEE,
        employee=employee,
    )
    db_session.add(user)
    db_session.flush()

    assert department.id is not None
    assert employee.id is not None
    assert user.id is not None
    assert employee.department is department
    assert department.employees == [employee]
    assert employee.user is user
    assert user.employee is employee
    assert employee.is_active is True
    assert user.is_active is True
    assert employee.created_at is not None
    assert user.created_at is not None


def test_department_name_is_unique(db_session: Session) -> None:
    db_session.add_all([Department(name="Operations"), Department(name="Operations")])

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_employee_email_is_unique(db_session: Session) -> None:
    department = Department(name="Finance")
    db_session.add_all(
        [
            Employee(
                first_name="Alex",
                last_name="One",
                email="duplicate.employee@example.com",
                hire_date=date(2024, 1, 1),
                department=department,
            ),
            Employee(
                first_name="Alex",
                last_name="Two",
                email="duplicate.employee@example.com",
                hire_date=date(2024, 1, 2),
                department=department,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_email_is_unique(db_session: Session) -> None:
    db_session.add_all(
        [
            User(
                email="duplicate.user@example.com",
                hashed_password="hash-one",
                role=UserRole.ADMIN,
            ),
            User(
                email="duplicate.user@example.com",
                hashed_password="hash-two",
                role=UserRole.MANAGER,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_employee_can_have_at_most_one_user(db_session: Session) -> None:
    employee = Employee(
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.com",
        hire_date=date(2023, 5, 1),
        department=Department(name="Research"),
    )
    db_session.add(employee)
    db_session.flush()

    db_session.add_all(
        [
            User(
                email="grace.one@example.com",
                hashed_password="hash-one",
                role=UserRole.MANAGER,
                employee_id=employee.id,
            ),
            User(
                email="grace.two@example.com",
                hashed_password="hash-two",
                role=UserRole.EMPLOYEE,
                employee_id=employee.id,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_employee_requires_an_existing_department(db_session: Session) -> None:
    employee = Employee(
        first_name="Katherine",
        last_name="Johnson",
        email="katherine@example.com",
        hire_date=date(2022, 8, 1),
        department_id=2_147_483_647,
    )
    db_session.add(employee)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_employee_reference_must_exist(db_session: Session) -> None:
    user = User(
        email="orphan.user@example.com",
        hashed_password="hash-value",
        role=UserRole.EMPLOYEE,
        employee_id=2_147_483_647,
    )
    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_employee_department_foreign_key_is_present(
    postgres_engine: Engine,
) -> None:
    foreign_keys = inspect(postgres_engine).get_foreign_keys("employees")

    assert any(
        foreign_key["referred_table"] == "departments"
        and foreign_key["constrained_columns"] == ["department_id"]
        for foreign_key in foreign_keys
    )
