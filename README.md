# Employee Management API

## Run the test suite

The integration tests use PostgreSQL and are intentionally pinned to the
`employee_management_test` database. Run them in Docker so the test runner can
reach PostgreSQL through the Compose service hostname `db`:

```bash
docker compose run --build --rm test
```

Set `POSTGRES_USER` and `POSTGRES_PASSWORD` in the local, untracked `.env` file
before running the command. The test runner creates `employee_management_test`
if it does not exist, applies Alembic migrations to that database, then runs
the suite. It never targets the development database.

The development API and its database can be started separately with
`docker compose up --build`.
