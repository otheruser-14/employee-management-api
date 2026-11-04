from collections.abc import Iterator
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import JWT_ALGORITHM, settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.main import app
from app.models import User, UserRole
from app.services.auth import AdminBootstrapClosedError, bootstrap_admin

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
TEST_PASSWORD = "correct horse battery staple"


@pytest.fixture
def auth_client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_user(db_session: Session) -> User:
    user = User(
        email="auth-user@example.com",
        hashed_password=hash_password(TEST_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_password_hashing_uses_argon2id() -> None:
    hashed_password = hash_password(TEST_PASSWORD)

    assert hashed_password.startswith("$argon2id$")
    assert hashed_password != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, hashed_password)
    assert not verify_password("incorrect password", hashed_password)


def test_login_returns_access_token(
    auth_client: TestClient,
    auth_user: User,
) -> None:
    response = auth_client.post(
        LOGIN_URL,
        json={"email": auth_user.email, "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    payload = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret.get_secret_value(),
        algorithms=[JWT_ALGORITHM],
    )
    assert payload["sub"] == str(auth_user.id)
    assert payload["exp"] > payload["iat"]
    assert "hashed_password" not in response.json()


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("auth-user@example.com", "wrong password"),
        ("unknown@example.com", TEST_PASSWORD),
    ],
)
def test_login_rejects_invalid_credentials(
    auth_client: TestClient,
    auth_user: User,
    email: str,
    password: str,
) -> None:
    response = auth_client.post(
        LOGIN_URL,
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    assert response.headers["www-authenticate"] == "Bearer"


def test_inactive_user_cannot_login(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    user = User(
        email="inactive@example.com",
        hashed_password=hash_password(TEST_PASSWORD),
        role=UserRole.EMPLOYEE,
        is_active=False,
    )
    db_session.add(user)
    db_session.flush()

    response = auth_client.post(
        LOGIN_URL,
        json={"email": user.email, "password": TEST_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_auth_me_returns_safe_user_fields(
    auth_client: TestClient,
    auth_user: User,
) -> None:
    token = create_access_token(auth_user.id)

    response = auth_client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": auth_user.id,
        "email": auth_user.email,
        "role": "admin",
        "is_active": True,
        "employee_id": None,
    }
    assert "hashed_password" not in response.json()


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token"])
def test_auth_me_requires_valid_token(
    auth_client: TestClient,
    authorization: str | None,
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}

    response = auth_client.get(ME_URL, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_me_rejects_expired_token(
    auth_client: TestClient,
    auth_user: User,
) -> None:
    expired_token = create_access_token(
        auth_user.id,
        expires_delta=timedelta(seconds=-1),
    )

    response = auth_client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_auth_me_rejects_token_signed_with_another_algorithm(
    auth_client: TestClient,
    auth_user: User,
) -> None:
    wrong_algorithm_token = jwt.encode(
        {"sub": str(auth_user.id), "exp": 4_102_444_800},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS512",
    )

    response = auth_client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {wrong_algorithm_token}"},
    )

    assert response.status_code == 401


def test_auth_me_rejects_inactive_user(
    auth_client: TestClient,
    db_session: Session,
    auth_user: User,
) -> None:
    auth_user.is_active = False
    db_session.flush()
    token = create_access_token(auth_user.id)

    response = auth_client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_openapi_documents_bearer_authentication() -> None:
    openapi = app.openapi()

    assert openapi["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_admin_bootstrap_creates_only_first_user(db_session: Session) -> None:
    created = bootstrap_admin(
        db_session,
        "first-admin@example.com",
        TEST_PASSWORD,
    )

    assert created.role is UserRole.ADMIN
    assert created.is_active
    assert verify_password(TEST_PASSWORD, created.hashed_password)

    with pytest.raises(AdminBootstrapClosedError):
        bootstrap_admin(db_session, "second-admin@example.com", TEST_PASSWORD)


def test_admin_bootstrap_refuses_when_any_user_exists(
    db_session: Session,
    auth_user: User,
) -> None:
    with pytest.raises(AdminBootstrapClosedError):
        bootstrap_admin(db_session, "new-admin@example.com", TEST_PASSWORD)


def test_public_registration_is_not_available(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "public@example.com", "password": TEST_PASSWORD},
    )

    assert response.status_code == 404


def test_login_validation_rejects_malformed_input(auth_client: TestClient) -> None:
    response = auth_client.post(
        LOGIN_URL,
        json={"email": "not-an-email", "password": ""},
    )

    assert response.status_code == 422
