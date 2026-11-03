import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail(
            "TEST_DATABASE_URL must point to a dedicated PostgreSQL test database."
        )

    parsed_url = make_url(database_url)
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.fail("Integration tests require PostgreSQL; SQLite is not supported.")
    if not parsed_url.database or not parsed_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with '_test'.")

    engine = create_engine(parsed_url, pool_pre_ping=True)
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
