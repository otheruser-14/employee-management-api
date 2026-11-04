from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models import Department, Employee

BASE_URL = "/api/v1/departments"


@pytest.fixture
def department_client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_department_crud_lifecycle(department_client: TestClient) -> None:
    created = department_client.post(
        BASE_URL,
        json={"name": "Engineering", "description": "Builds products"},
    )

    assert created.status_code == 201
    department = created.json()
    assert department["name"] == "Engineering"
    assert department["description"] == "Builds products"
    assert department["id"]
    assert department["created_at"]
    assert department["updated_at"]

    department_id = department["id"]
    fetched = department_client.get(f"{BASE_URL}/{department_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == department_id

    updated = department_client.patch(
        f"{BASE_URL}/{department_id}",
        json={"name": "Product Engineering"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Product Engineering"
    assert updated.json()["description"] == "Builds products"

    deleted = department_client.delete(f"{BASE_URL}/{department_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert department_client.get(f"{BASE_URL}/{department_id}").status_code == 404


def test_department_list_is_paginated(department_client: TestClient) -> None:
    for name in ("Finance", "Operations", "Research"):
        response = department_client.post(BASE_URL, json={"name": name})
        assert response.status_code == 201

    first_page = department_client.get(BASE_URL, params={"page": 1, "page_size": 2})
    second_page = department_client.get(BASE_URL, params={"page": 2, "page_size": 2})

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["page"] == 1
    assert len(first_page.json()["items"]) == 2
    assert second_page.json()["page"] == 2
    assert len(second_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["id"] < first_page.json()["items"][1]["id"]


def test_duplicate_department_name_returns_conflict(
    department_client: TestClient,
) -> None:
    assert department_client.post(BASE_URL, json={"name": "Legal"}).status_code == 201

    duplicate = department_client.post(BASE_URL, json={"name": "Legal"})

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "A department with this name already exists"


def test_update_to_existing_name_returns_conflict(
    department_client: TestClient,
) -> None:
    first = department_client.post(BASE_URL, json={"name": "Sales"}).json()
    department_client.post(BASE_URL, json={"name": "Support"})

    response = department_client.patch(
        f"{BASE_URL}/{first['id']}",
        json={"name": "Support"},
    )

    assert response.status_code == 409


def test_department_with_employees_cannot_be_deleted(
    department_client: TestClient,
    db_session: Session,
) -> None:
    department = Department(name="People")
    employee = Employee(
        first_name="Jordan",
        last_name="Lee",
        email="jordan.lee@example.com",
        hire_date=date(2025, 1, 1),
        department=department,
    )
    db_session.add(employee)
    db_session.flush()

    response = department_client.delete(f"{BASE_URL}/{department.id}")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Department cannot be deleted while employees are assigned"
    )


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"name": ""}, 422),
        ({"name": "x" * 101}, 422),
        ({"name": None}, 422),
        ({}, 422),
    ],
)
def test_department_create_validation(
    department_client: TestClient,
    payload: dict[str, object],
    expected_status: int,
) -> None:
    response = department_client.post(BASE_URL, json=payload)

    assert response.status_code == expected_status


def test_invalid_pagination_returns_validation_error(
    department_client: TestClient,
) -> None:
    response = department_client.get(BASE_URL, params={"page": 0, "page_size": 101})

    assert response.status_code == 422


def test_unknown_department_returns_not_found(
    department_client: TestClient,
) -> None:
    assert department_client.get(f"{BASE_URL}/999999").status_code == 404
    assert (
        department_client.patch(
            f"{BASE_URL}/999999",
            json={"name": "Missing"},
        ).status_code
        == 404
    )
    assert department_client.delete(f"{BASE_URL}/999999").status_code == 404
