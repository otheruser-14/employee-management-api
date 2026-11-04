import os
import secrets

import pytest
from sqlalchemy import create_engine, text

if not os.environ.get("JWT_SECRET"):
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)

from app.core.config import settings

TEST_DATABASE_NAME = "employee_management_test"


def ensure_test_database() -> None:
    if settings.database_name != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"Test runner must use {TEST_DATABASE_NAME}, not {settings.database_name}."
        )

    admin_engine = create_engine(
        settings.database_url.set(database="postgres"),
        pool_pre_ping=True,
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_NAME},
            ).scalar_one_or_none()
            if exists is None:
                connection.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"')
                )
    finally:
        admin_engine.dispose()


if __name__ == "__main__":
    ensure_test_database()
    raise SystemExit(pytest.main(["-q"]))
