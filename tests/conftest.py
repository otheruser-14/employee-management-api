from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import settings

TEST_DATABASE_NAME = "employee_management_test"


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    if settings.database_name != TEST_DATABASE_NAME:
        pytest.fail(
            "Tests require employee_management_test. Run "
            "'docker compose run --build --rm test' to use the isolated test database."
        )

    database_url = settings.database_url
    if not database_url.drivername.startswith("postgresql"):
        pytest.fail("Integration tests require PostgreSQL; SQLite is not supported.")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            alembic_config = Config("alembic.ini")
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(postgres_engine: Engine) -> Iterator[Session]:
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
