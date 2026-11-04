from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Department, Employee, User, UserRole

EMPLOYEES_URL = "/api/v1/employees"
DEPARTMENTS_URL = "/api/v1/departments"


@pytest.fixture
def rbac_client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def make_employee(
    db_session: Session,
    department: Department,
    email: str,
) -> Employee:
    employee = Employee(
        first_name="Alex",
        last_name="Rivera",
        email=email,
        hire_date=date(2024, 1, 15),
        department_id=department.id,
    )
    db_session.add(employee)
    db_session.flush()
    return employee


def make_user(
    db_session: Session,
    role: UserRole,
    email: str,
    *,
    employee_id: int | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password="unused-test-hash",
        role=role,
        is_active=True,
        employee_id=employee_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def authorization(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def employee_payload(department_id: int) -> dict[str, object]:
    return {
        "first_name": "New",
        "last_name": "Hire",
        "email": "new-hire@example.com",
        "hire_date": "2025-02-01",
        "department_id": department_id,
    }


def test_admin_has_full_department_and_employee_access(
    rbac_client: TestClient,
    db_session: Session,
) -> None:
    department = Department(name="Engineering")
    db_session.add(department)
    db_session.flush()
    employee = make_employee(db_session, department, "admin-target@example.com")
    admin = make_user(db_session, UserRole.ADMIN, "rbac-admin@example.com")
    headers = authorization(admin)

    assert (
        rbac_client.post(
            DEPARTMENTS_URL,
            json={"name": "Finance"},
            headers=headers,
        ).status_code
        == 201
    )
    assert rbac_client.get(DEPARTMENTS_URL, headers=headers).status_code == 200
    assert (
        rbac_client.patch(
            f"{DEPARTMENTS_URL}/{department.id}",
            json={"description": "Updated"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        rbac_client.delete(
            f"{DEPARTMENTS_URL}/{department.id}",
            headers=headers,
        ).status_code
        == 409
    )

    created = rbac_client.post(
        EMPLOYEES_URL,
        json=employee_payload(department.id),
        headers=headers,
    )
    assert created.status_code == 201
    assert rbac_client.get(EMPLOYEES_URL, headers=headers).status_code == 200
    assert (
        rbac_client.get(
            f"{EMPLOYEES_URL}/{employee.id}",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        rbac_client.patch(
            f"{EMPLOYEES_URL}/{employee.id}",
            json={"job_title": "Architect"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        rbac_client.delete(
            f"{EMPLOYEES_URL}/{employee.id}",
            headers=headers,
        ).status_code
        == 204
    )


def test_manager_can_read_and_update_but_not_create_or_delete_employees(
    rbac_client: TestClient,
    db_session: Session,
) -> None:
    department = Department(name="People")
    db_session.add(department)
    db_session.flush()
    employee = make_employee(db_session, department, "manager-target@example.com")
    manager = make_user(db_session, UserRole.MANAGER, "rbac-manager@example.com")
    headers = authorization(manager)

    assert rbac_client.get(EMPLOYEES_URL, headers=headers).status_code == 200
    assert (
        rbac_client.get(
            f"{EMPLOYEES_URL}/{employee.id}",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        rbac_client.patch(
            f"{EMPLOYEES_URL}/{employee.id}",
            json={"job_title": "Team Lead"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        rbac_client.post(
            EMPLOYEES_URL,
            json=employee_payload(department.id),
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        rbac_client.delete(
            f"{EMPLOYEES_URL}/{employee.id}",
            headers=headers,
        ).status_code
        == 403
    )

    assert rbac_client.get(DEPARTMENTS_URL, headers=headers).status_code == 403
    assert (
        rbac_client.get(
            f"{DEPARTMENTS_URL}/{department.id}",
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        rbac_client.post(
            DEPARTMENTS_URL,
            json={"name": "Operations"},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        rbac_client.patch(
            f"{DEPARTMENTS_URL}/{department.id}",
            json={"name": "Operations"},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        rbac_client.delete(
            f"{DEPARTMENTS_URL}/{department.id}",
            headers=headers,
        ).status_code
        == 403
    )


def test_employee_can_only_read_own_profile(
    rbac_client: TestClient,
    db_session: Session,
) -> None:
    department = Department(name="Support")
    db_session.add(department)
    db_session.flush()
    own_employee = make_employee(db_session, department, "self@example.com")
    other_employee = make_employee(db_session, department, "other@example.com")
    user = make_user(
        db_session,
        UserRole.EMPLOYEE,
        "rbac-employee@example.com",
        employee_id=own_employee.id,
    )
    headers = authorization(user)

    own_profile = rbac_client.get(
        f"{EMPLOYEES_URL}/{own_employee.id}",
        headers=headers,
    )
    assert own_profile.status_code == 200
    assert own_profile.json()["id"] == own_employee.id
    assert (
        rbac_client.get(
            f"{EMPLOYEES_URL}/{other_employee.id}",
            headers=headers,
        ).status_code
        == 403
    )
    assert rbac_client.get(EMPLOYEES_URL, headers=headers).status_code == 403
    assert (
        rbac_client.post(
            EMPLOYEES_URL,
            json=employee_payload(department.id),
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        rbac_client.patch(
            f"{EMPLOYEES_URL}/{own_employee.id}",
            json={"job_title": "Not allowed"},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        rbac_client.delete(
            f"{EMPLOYEES_URL}/{own_employee.id}",
            headers=headers,
        ).status_code
        == 403
    )
    assert rbac_client.get(DEPARTMENTS_URL, headers=headers).status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", EMPLOYEES_URL),
        ("get", DEPARTMENTS_URL),
    ],
)
def test_protected_routes_require_authentication(
    rbac_client: TestClient,
    method: str,
    path: str,
) -> None:
    response = getattr(rbac_client, method)(path)

    assert response.status_code == 401
