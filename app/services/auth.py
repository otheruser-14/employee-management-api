from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_unknown_user_password,
)
from app.models import User, UserRole

USER_EMAIL_CONSTRAINT = "uq_users_email"
_ADMIN_BOOTSTRAP_LOCK_ID = 824_051_902_184


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AdminBootstrapClosedError(Exception):
    pass


class AdminEmailConflictError(Exception):
    pass


def login(db: Session, email: str, password: str) -> str:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_unknown_user_password(password)
        raise InvalidCredentialsError
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError
    if not user.is_active:
        raise InactiveUserError
    return create_access_token(user.id)


def bootstrap_admin(db: Session, email: str, password: str) -> User:
    db.execute(select(func.pg_advisory_xact_lock(_ADMIN_BOOTSTRAP_LOCK_ID)))
    existing_user = db.scalar(select(User.id).limit(1))
    if existing_user is not None:
        db.rollback()
        raise AdminBootstrapClosedError

    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint_name = getattr(
            getattr(error.orig, "diag", None),
            "constraint_name",
            None,
        )
        if constraint_name == USER_EMAIL_CONSTRAINT:
            raise AdminEmailConflictError from error
        raise
    db.refresh(user)
    return user
