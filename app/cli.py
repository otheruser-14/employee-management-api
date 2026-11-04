import argparse
import getpass
import sys
from typing import Annotated

from pydantic import EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.services.auth import (
    AdminBootstrapClosedError,
    AdminEmailConflictError,
    bootstrap_admin,
)

_MINIMUM_PASSWORD_LENGTH = 12


def create_admin() -> int:
    try:
        email = str(
            TypeAdapter(Annotated[EmailStr, Field(max_length=320)]).validate_python(
                input("Admin email: ").strip()
            )
        )
    except (EOFError, ValidationError):
        print("A valid admin email is required.", file=sys.stderr)
        return 2

    password = getpass.getpass("Admin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if len(password) < _MINIMUM_PASSWORD_LENGTH:
        print("Admin password must be at least 12 characters.", file=sys.stderr)
        return 2
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        try:
            bootstrap_admin(db, email, password)
        except AdminBootstrapClosedError:
            print(
                "Admin bootstrap is closed because a user already exists.",
                file=sys.stderr,
            )
            return 1
        except AdminEmailConflictError:
            print("An account already uses that email address.", file=sys.stderr)
            return 1
        except SQLAlchemyError:
            print("Database error while creating the initial admin.", file=sys.stderr)
            return 1

    print("Initial admin account created.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage initial API bootstrap.")
    parser.add_argument("command", choices=["create-admin"])
    args = parser.parse_args()
    if args.command == "create-admin":
        return create_admin()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
