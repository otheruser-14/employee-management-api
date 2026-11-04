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

## Authentication setup

Set `JWT_SECRET` in the local, untracked `.env` file to a cryptographically
random value of at least 32 characters. Generate one with:

```bash
openssl rand -hex 32
```

The API will not start with a missing or too-short signing key. Access tokens
use HS256 and expire after 15 minutes by default; configure
`ACCESS_TOKEN_EXPIRE_MINUTES` from 1 to 1440 to change the lifetime.

There is no public account-registration endpoint. Create the initial admin
once, using an interactive password prompt, with:

```bash
docker compose exec api python -m app.cli create-admin
```

The bootstrap command refuses to create an admin if any user already exists.
Login accepts JSON credentials at `POST /api/v1/auth/login`; the returned
`access_token` can be entered in the Swagger UI Authorize dialog.
