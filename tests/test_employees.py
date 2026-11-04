from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models import Department, Employee

BASE_URL = "/api/v1/employees"


@pytest.fixture
def employee_client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def department(db_session: Session) -> Department:
    department = Department(name="Engineering")
    db_session.add(department)
    db_session.flush()
    return department


def employee_payload(
    department_id: int,
    *,
    email: str = "employee@example.com",
) -> dict[str, object]:
    return {
        "first_name": "Taylor",
        "last_name": "Morgan",
        "email": email,
        "hire_date": "2024-06-15",
        "department_id": department_id,
        "phone": "+1-555-0100",
        "job_title": "Backend Developer",
    }


def test_employee_create_retrieve_update_delete(
    employee_client: TestClient,
    department: Department,
) -> None:
    created = employee_client.post(BASE_URL, json=employee_payload(department.id))

    assert created.status_code == 201
    employee = created.json()
    employee_id = employee["id"]
    assert employee["first_name"] == "Taylor"
    assert employee["email"] == "employee@example.com"
    assert employee["hire_date"] == "2024-06-15"
    assert employee["department_id"] == department.id
    assert employee["is_active"] is True
    assert employee["created_at"]
    assert employee["updated_at"]

    fetched = employee_client.get(f"{BASE_URL}/{employee_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == employee_id

    updated = employee_client.patch(
        f"{BASE_URL}/{employee_id}",
        json={"job_title": "Senior Developer", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["job_title"] == "Senior Developer"
    assert updated.json()["is_active"] is False
    assert updated.json()["first_name"] == "Taylor"

    deleted = employee_client.delete(f"{BASE_URL}/{employee_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert employee_client.get(f"{BASE_URL}/{employee_id}").status_code == 404


def test_employee_listing_is_paginated(
    employee_client: TestClient,
    department: Department,
) -> None:
    for number in range(3):
        response = employee_client.post(
            BASE_URL,
            json=employee_payload(
                department.id,
                email=f"employee-{number}@example.com",
            ),
        )
        assert response.status_code == 201

    first_page = employee_client.get(BASE_URL, params={"page": 1, "page_size": 2})
    second_page = employee_client.get(BASE_URL, params={"page": 2, "page_size": 2})

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 2
    assert second_page.json()["total"] == 3
    assert len(second_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["id"] < first_page.json()["items"][1]["id"]


def test_employee_list_can_be_filtered_by_department(
    employee_client: TestClient,
    db_session: Session,
    department: Department,
) -> None:
    other_department = Department(name="Finance")
    db_session.add(other_department)
    db_session.flush()
    assert (
        employee_client.post(
            BASE_URL,
            json=employee_payload(department.id, email="eng@example.com"),
        ).status_code
        == 201
    )
    assert (
        employee_client.post(
            BASE_URL,
            json=employee_payload(other_department.id, email="finance@example.com"),
        ).status_code
        == 201
    )

    response = employee_client.get(
        BASE_URL,
        params={"department_id": other_department.id},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["email"] == "finance@example.com"
    assert response.json()["items"][0]["department_id"] == other_department.id


def test_duplicate_employee_email_returns_conflict(
    employee_client: TestClient,
    department: Department,
) -> None:
    assert (
        employee_client.post(
            BASE_URL,
            json=employee_payload(department.id),
        ).status_code
        == 201
    )

    duplicate = employee_client.post(BASE_URL, json=employee_payload(department.id))

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "An employee with this email already exists"


def test_update_to_existing_email_returns_conflict(
    employee_client: TestClient,
    department: Department,
) -> None:
    first = employee_client.post(
        BASE_URL,
        json=employee_payload(department.id, email="first@example.com"),
    ).json()
    employee_client.post(
        BASE_URL,
        json=employee_payload(department.id, email="second@example.com"),
    )

    response = employee_client.patch(
        f"{BASE_URL}/{first['id']}",
        json={"email": "second@example.com"},
    )

    assert response.status_code == 409


def test_nonexistent_department_id_returns_not_found(
    employee_client: TestClient,
) -> None:
    response = employee_client.post(
        BASE_URL,
        json=employee_payload(2_147_483_647),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"


def test_update_to_nonexistent_department_returns_not_found(
    employee_client: TestClient,
    department: Department,
) -> None:
    created = employee_client.post(BASE_URL, json=employee_payload(department.id))

    response = employee_client.patch(
        f"{BASE_URL}/{created.json()['id']}",
        json={"department_id": 2_147_483_647},
    )

    assert response.status_code == 404


def test_unknown_employee_returns_not_found(employee_client: TestClient) -> None:
    assert employee_client.get(f"{BASE_URL}/999999").status_code == 404
    assert (
        employee_client.patch(
            f"{BASE_URL}/999999", json={"first_name": "Unknown"}
        ).status_code
        == 404
    )
    assert employee_client.delete(f"{BASE_URL}/999999").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"first_name": "", "last_name": "Morgan"},
        {"first_name": "Taylor", "last_name": "Morgan", "email": "not-an-email"},
        {"first_name": "Taylor", "last_name": "Morgan", "email": "a" * 321},
    ],
)
def test_employee_create_validation_errors(
    employee_client: TestClient,
    payload: dict[str, object],
) -> None:
    response = employee_client.post(BASE_URL, json=payload)

    assert response.status_code == 422


def test_employee_update_rejects_null_required_field(
    employee_client: TestClient,
    department: Department,
) -> None:
    created = employee_client.post(BASE_URL, json=employee_payload(department.id))

    response = employee_client.patch(
        f"{BASE_URL}/{created.json()['id']}",
        json={"department_id": None},
    )

    assert response.status_code == 422


def test_employee_department_relationship_is_persisted(
    db_session: Session,
    department: Department,
) -> None:
    employee = Employee(
        first_name="Sam",
        last_name="Rivera",
        email="sam@example.com",
        hire_date=date(2023, 10, 1),
        department_id=department.id,
    )
    db_session.add(employee)
    db_session.flush()

    assert employee.department.id == department.id
