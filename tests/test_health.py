from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ready_when_database_is_available(
    client: TestClient,
) -> None:
    db = Mock(spec=Session)
    app.dependency_overrides[get_db] = lambda: db

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    db.execute.assert_called_once()


def test_ready_returns_service_unavailable_when_database_fails(
    client: TestClient,
) -> None:
    db = Mock(spec=Session)
    db.execute.side_effect = SQLAlchemyError("database unavailable")
    app.dependency_overrides[get_db] = lambda: db

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
